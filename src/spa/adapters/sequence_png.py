"""Independent native-representation observations of sequence PNG bytes."""

import struct
import zlib
from io import BytesIO
from typing import Literal

from PIL import Image, UnidentifiedImageError

from spa.adapters.png_input import _encoded_chunks, _entries, _inflate, _profile
from spa.contracts.encoded_animation import AnimationDecodeError, DecodedSequencePng


def _verify_samples(
    chunks: dict[bytes, bytes],
    width: int,
    height: int,
    color_type: int,
    depth: int,
    interlace: int,
) -> None:
    # Pillow owns unfiltering and Adam7. Check complete packed scanlines first;
    # its decoder can otherwise tolerate an extended or truncated zlib stream.
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
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
            rows.append(((pass_width * channels * depth + 7) // 8 + 1, pass_height))
    expected = sum(stride * count for stride, count in rows)
    stream = _inflate(chunks[b"IDAT"], expected)
    if len(stream) != expected:
        raise ValueError("PNG pixel stream size disagrees with IHDR")
    offset = 0
    for stride, count in rows:
        for _ in range(count):
            if stream[offset] > 4:
                raise ValueError("Invalid PNG scanline filter")
            offset += stride


def decode_sequence_png(payload: bytes) -> DecodedSequencePng:
    """Decode supported PNG samples without defining source or export policy."""
    try:
        chunks = _encoded_chunks(payload)
        if len(chunks.get(b"IHDR", b"")) != 13:
            raise ValueError("Invalid PNG IHDR")
        width, height, depth, color_type, compression, filtering, interlace = (
            struct.unpack(">IIBBBBB", chunks[b"IHDR"])
        )
        if not 0 < width <= 0x7FFFFFFF or not 0 < height <= 0x7FFFFFFF:
            raise ValueError("Invalid PNG dimensions")
        if color_type not in (0, 2, 3, 4, 6) or (
            depth not in (1, 2, 4, 8) if color_type == 3 else depth != 8
        ):
            raise ValueError(
                "PNG requires 8-bit channels or 1/2/4/8-bit Palette Indexes"
            )
        if compression != 0 or filtering != 0 or interlace not in (0, 1):
            raise ValueError("Unsupported PNG encoding method")
        if color_type in (0, 4):
            if b"PLTE" in chunks:
                raise ValueError("Grayscale PNG cannot contain PLTE")
            alpha = chunks.get(b"tRNS")
            if alpha is not None and (
                color_type != 0
                or len(alpha) != 2
                or struct.unpack(">H", alpha)[0] > 255
            ):
                raise ValueError("Invalid Grayscale PNG tRNS")
            entries = ()
        else:
            entries = _entries(chunks, color_type)
        if color_type == 3 and len(entries) > 2**depth:
            raise ValueError("PNG PLTE exceeds bit depth")
        profile, icc = _profile(chunks)
        with Image.open(BytesIO(payload)) as image:
            expected_mode = {0: "L", 2: "RGB", 3: "P", 4: "LA", 6: "RGBA"}[color_type]
            if (
                image.format != "PNG"
                or image.mode != expected_mode
                or image.size != (width, height)
            ):
                raise ValueError(
                    "PNG decoder representation disagrees with encoded facts"
                )
            _verify_samples(chunks, width, height, color_type, depth, interlace)
            image.load()
            mode: Literal["rgb", "grayscale", "indexed"]
            rgba = image.convert("RGBA").tobytes()
            if color_type == 3:
                mode, stored = "indexed", image.tobytes()
                if any(index >= len(entries) for index in stored):
                    raise ValueError("PNG pixel index exceeds PLTE")
            elif color_type in (0, 4):
                mode, stored = "grayscale", image.convert("LA").tobytes()
            else:
                mode, stored = "rgb", rgba
            return DecodedSequencePng(
                width,
                height,
                mode,
                color_type,
                depth,
                stored,
                rgba,
                entries,
                profile,
                icc,
                chunks[b"sRGB"][0] if b"sRGB" in chunks else None,
            )
    except (
        OSError,
        ValueError,
        SyntaxError,
        zlib.error,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        raise AnimationDecodeError(str(exc)) from exc
