"""Independent encoded facts and complete pixels for external PNG input."""

import struct
import zlib
from io import BytesIO
from typing import Literal

from PIL import Image, PngImagePlugin, UnidentifiedImageError

from spa.adapters.icc import verify_icc
from spa.contracts.ports import PngInputError, PngInputFacts

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_COLOR_CHUNKS = (b"sRGB", b"iCCP", b"gAMA", b"cHRM")
_SRGB_GAMMA = struct.pack(">I", 45455)
_SRGB_CHROMATICITY = struct.pack(
    ">8I", 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000
)


def _encoded_chunks(payload: bytes) -> dict[bytes, bytes]:
    if not payload.startswith(_PNG_SIGNATURE):
        raise ValueError("PNG signature is absent")
    chunks: dict[bytes, bytes] = {}
    offset = len(_PNG_SIGNATURE)
    seen_idat = False
    idat_ended = False
    idat: list[bytes] = []
    while offset < len(payload):
        if len(payload) - offset < 12:
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", payload, offset)[0]
        end = offset + 12 + length
        if length > 0x7FFFFFFF or end > len(payload):
            raise ValueError("Invalid PNG chunk length")
        kind = payload[offset + 4 : offset + 8]
        if (
            any(not (65 <= value <= 90 or 97 <= value <= 122) for value in kind)
            or kind[2] & 0x20
        ):
            raise ValueError("Invalid PNG chunk type")
        data = payload[offset + 8 : end - 4]
        if zlib.crc32(kind + data) != struct.unpack_from(">I", payload, end - 4)[0]:
            raise ValueError("Invalid PNG chunk CRC")
        if offset == len(_PNG_SIGNATURE) and (kind != b"IHDR" or length != 13):
            raise ValueError("Invalid PNG IHDR")
        if kind == b"IDAT":
            if idat_ended:
                raise ValueError("Nonconsecutive PNG IDAT")
            seen_idat = True
            idat.append(data)
        elif kind == b"IEND":
            if not seen_idat or length != 0 or end != len(payload):
                raise ValueError("Invalid PNG IEND")
            chunks[b"IDAT"] = b"".join(idat)
            return chunks
        else:
            if seen_idat:
                idat_ended = True
            if kind in (b"acTL", b"fcTL", b"fdAT"):
                raise ValueError("Animated PNG input is unsupported")
            if kind in (b"cICP", b"mDCV", b"cLLI", b"eXIf"):
                raise ValueError("Unsupported PNG color metadata")
            if kind in (b"IHDR", b"PLTE", b"tRNS", *_COLOR_CHUNKS):
                if kind in chunks:
                    raise ValueError("Duplicate PNG " + kind.decode("ascii"))
                if kind != b"IHDR" and seen_idat:
                    raise ValueError("Invalid PNG chunk order")
                if kind in _COLOR_CHUNKS and b"PLTE" in chunks:
                    raise ValueError("PNG color metadata must precede PLTE")
                if kind == b"PLTE" and b"tRNS" in chunks:
                    raise ValueError("PNG PLTE must precede tRNS")
                chunks[kind] = data
            elif kind[0] & 0x20 == 0:
                raise ValueError("Unsupported critical PNG chunk")
        offset = end
    raise ValueError("PNG IEND is absent")


def _profile(
    chunks: dict[bytes, bytes],
) -> tuple[Literal["none", "srgb", "icc"], bytes | None]:
    if b"sRGB" in chunks:
        if len(chunks[b"sRGB"]) != 1 or chunks[b"sRGB"][0] > 3:
            raise ValueError("Invalid PNG sRGB intent")
        if b"iCCP" in chunks:
            raise ValueError("Conflicting PNG sRGB and ICC metadata")
        if b"gAMA" in chunks and chunks[b"gAMA"] != _SRGB_GAMMA:
            raise ValueError("PNG gAMA disagrees with sRGB")
        if b"cHRM" in chunks and chunks[b"cHRM"] != _SRGB_CHROMATICITY:
            raise ValueError("PNG cHRM disagrees with sRGB")
        return "srgb", None
    if b"gAMA" in chunks or b"cHRM" in chunks:
        raise ValueError("Unsupported PNG gAMA/cHRM metadata combination")
    if b"iCCP" not in chunks:
        return "none", None
    name, separator, compressed = chunks[b"iCCP"].partition(b"\x00")
    if (
        not separator
        or not 1 <= len(name) <= 79
        or any(not (32 <= value <= 126 or 161 <= value <= 255) for value in name)
        or name.startswith(b" ")
        or name.endswith(b" ")
        or b"  " in name
        or not compressed.startswith(b"\x00")
    ):
        raise ValueError("Invalid PNG iCCP encoding")
    profile = _inflate(compressed[1:], PngImagePlugin.MAX_TEXT_CHUNK)
    if len(profile) < 128 or struct.unpack_from(">I", profile)[0] != len(profile):
        raise ValueError("Invalid ICC declared size")
    if verify_icc(profile).color_space != "RGB":
        raise ValueError("PNG ICC must describe RGB colors")
    return "icc", profile


def _inflate(compressed: bytes, limit: int) -> bytes:
    stream = zlib.decompressobj()
    decoded = stream.decompress(compressed, limit + 1)
    if (
        len(decoded) > limit
        or not stream.eof
        or stream.unused_data
        or stream.unconsumed_tail
    ):
        raise ValueError("Invalid or oversized PNG compressed stream")
    return decoded


def _verify_pixel_stream(
    compressed: bytes, width: int, height: int, color_type: int, interlace: int
) -> None:
    # Validate the encoded stream that Pillow can tolerate truncating or extending.
    # Pillow still owns unfiltering, Adam7 reconstruction, and pixel decoding.
    channels = {2: 3, 3: 1, 6: 4}[color_type]
    passes = (
        ((0, 0, 1, 1),)
        if interlace == 0
        else (
            (0, 0, 8, 8),
            (4, 0, 8, 8),
            (0, 4, 4, 8),
            (2, 0, 4, 4),
            (0, 2, 2, 4),
            (1, 0, 2, 2),
            (0, 1, 1, 2),
        )
    )
    rows: list[tuple[int, int]] = []
    for x, y, dx, dy in passes:
        pass_width = max(0, (width - x + dx - 1) // dx)
        pass_height = max(0, (height - y + dy - 1) // dy)
        if pass_width and pass_height:
            rows.append((pass_width * channels + 1, pass_height))
    expected = sum(row_size * count for row_size, count in rows)
    decoded = _inflate(compressed, expected)
    if len(decoded) != expected:
        raise ValueError("PNG pixel stream size disagrees with IHDR")
    offset = 0
    for row_size, count in rows:
        for _ in range(count):
            if decoded[offset] > 4:
                raise ValueError("Invalid PNG scanline filter")
            offset += row_size


def _entries(
    chunks: dict[bytes, bytes], color_type: int
) -> tuple[tuple[int, int, int, int], ...]:
    palette = chunks.get(b"PLTE")
    alpha = chunks.get(b"tRNS")
    if palette is not None and (not palette or len(palette) % 3 or len(palette) > 768):
        raise ValueError("Invalid PNG PLTE")
    if color_type == 3:
        if palette is None:
            raise ValueError("Indexed PNG PLTE is absent")
        if alpha is not None and (not alpha or len(alpha) > len(palette) // 3):
            raise ValueError("Invalid Indexed PNG tRNS")
        return tuple(
            (
                palette[index],
                palette[index + 1],
                palette[index + 2],
                alpha[index // 3]
                if alpha is not None and index // 3 < len(alpha)
                else 255,
            )
            for index in range(0, len(palette), 3)
        )
    if alpha is not None and (
        color_type != 2
        or len(alpha) != 6
        or any(value > 255 for value in struct.unpack(">3H", alpha))
    ):
        raise ValueError("Invalid RGB PNG tRNS")
    return ()


def decode_png_input(payload: bytes) -> PngInputFacts:
    try:
        chunks = _encoded_chunks(payload)
        width, height, bit_depth, color_type, compression, filtering, interlace = (
            struct.unpack(">IIBBBBB", chunks[b"IHDR"])
        )
        if not 0 < width <= 0x7FFFFFFF or not 0 < height <= 0x7FFFFFFF:
            raise ValueError("Invalid PNG dimensions")
        if bit_depth != 8 or color_type not in (2, 3, 6):
            raise ValueError("PNG input requires 8-bit RGB, RGBA, or Indexed samples")
        if compression != 0 or filtering != 0 or interlace not in (0, 1):
            raise ValueError("Unsupported PNG encoding method")
        entries = _entries(chunks, color_type)
        profile, icc = _profile(chunks)
        with Image.open(BytesIO(payload)) as image:
            expected_mode = {2: "RGB", 3: "P", 6: "RGBA"}[color_type]
            if (
                image.format != "PNG"
                or image.mode != expected_mode
                or image.size != (width, height)
            ):
                raise ValueError(
                    "PNG decoder representation disagrees with encoded facts"
                )
            _verify_pixel_stream(chunks[b"IDAT"], width, height, color_type, interlace)
            image.load()
            stored = image.tobytes()
            if color_type == 3 and any(index >= len(entries) for index in stored):
                raise ValueError("PNG pixel index exceeds PLTE")
            rgba = image.convert("RGBA").tobytes()
            return PngInputFacts(
                width,
                height,
                "indexed" if color_type == 3 else "rgb",
                rgba,
                stored if color_type == 3 else rgba,
                entries,
                profile,
                icc,
            )
    except (
        OSError,
        ValueError,
        SyntaxError,
        zlib.error,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        raise PngInputError(str(exc)) from exc
