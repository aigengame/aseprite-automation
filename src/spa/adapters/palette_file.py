"""Independent Palette-file observations; native Aseprite owns Palette creation."""

import hashlib
import io
import re
import struct
import zlib
from typing import Literal

from PIL import Image, UnidentifiedImageError

from spa.contracts.ports import PaletteFileError, PaletteFileFacts

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _gpl_entries(payload: bytes) -> tuple[tuple[int, int, int, int], ...]:
    lines = payload.decode("utf-8").splitlines()
    if not lines or lines[0].strip() != "GIMP Palette":
        raise ValueError("GPL header is absent")
    channels = 3
    channel_declared = False
    entries: list[tuple[int, int, int, int]] = []
    for number, text in enumerate(lines[1:], start=2):
        line = text.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line and not line[0].isdigit():
            if entries:
                raise ValueError(f"GPL metadata after color at line {number}")
            name, value = (part.strip() for part in line.split(":", 1))
            if name not in ("Name", "Columns", "Channels"):
                raise ValueError(f"Unsupported GPL metadata at line {number}")
            if name == "Channels":
                if channel_declared or value not in ("RGB", "RGBA"):
                    raise ValueError(f"Unsupported GPL Channels at line {number}")
                channels = len(value)
                channel_declared = True
            continue
        parts = line.split(maxsplit=channels)
        if len(parts) < channels or any(
            re.fullmatch(r"[0-9]+", value) is None for value in parts[:channels]
        ):
            raise ValueError(f"Malformed GPL color at line {number}")
        values = [int(value) for value in parts[:channels]]
        if any(value > 255 for value in values):
            raise ValueError(f"GPL component outside 0..255 at line {number}")
        if channels == 3:
            values.append(255)
        entries.append((values[0], values[1], values[2], values[3]))
    if not entries:
        raise ValueError("Palette file has no Entries")
    return tuple(entries)


def _png_entries(payload: bytes) -> tuple[tuple[int, int, int, int], ...]:
    if not payload.startswith(_PNG_SIGNATURE):
        raise ValueError("PNG signature is absent")
    offset = len(_PNG_SIGNATURE)
    palette: bytes | None = None
    alpha = b""
    bit_depth: int | None = None
    seen_idat = False
    idat_ended = False
    seen_iend = False
    while offset < len(payload):
        if len(payload) - offset < 12:
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", payload, offset)[0]
        end = offset + 12 + length
        if end > len(payload):
            raise ValueError("Truncated PNG chunk")
        kind = payload[offset + 4 : offset + 8]
        if (
            any(
                not (65 <= character <= 90 or 97 <= character <= 122)
                for character in kind
            )
            or kind[2] & 0x20
        ):
            raise ValueError("Invalid PNG chunk type")
        data = payload[offset + 8 : offset + 8 + length]
        checksum = struct.unpack_from(">I", payload, offset + 8 + length)[0]
        if zlib.crc32(kind + data) != checksum:
            raise ValueError("Invalid PNG chunk CRC")
        if offset == len(_PNG_SIGNATURE):
            if kind != b"IHDR" or length != 13:
                raise ValueError("Invalid PNG IHDR")
            width, height, bit_depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", data)
            )
            if (
                width == 0
                or height == 0
                or color_type != 3
                or bit_depth not in (1, 2, 4, 8)
                or compression != 0
                or filtering != 0
                or interlace not in (0, 1)
            ):
                raise ValueError("PNG must use valid Indexed Color Type 3")
        elif kind == b"IHDR":
            raise ValueError("Duplicate PNG IHDR")
        elif kind == b"PLTE":
            if (
                palette is not None
                or seen_idat
                or length == 0
                or length % 3
                or length > 768
            ):
                raise ValueError("Invalid PNG PLTE")
            if bit_depth is None or length // 3 > 2**bit_depth:
                raise ValueError("PNG PLTE exceeds bit depth")
            palette = data
        elif kind == b"tRNS":
            if (
                palette is None
                or seen_idat
                or alpha
                or length == 0
                or length > len(palette) // 3
            ):
                raise ValueError("Invalid PNG tRNS")
            alpha = data
        elif kind == b"IDAT":
            if palette is None or idat_ended:
                raise ValueError("Invalid PNG IDAT order")
            seen_idat = True
        elif kind == b"IEND":
            if not seen_idat or length != 0 or end != len(payload):
                raise ValueError("Invalid PNG IEND")
            seen_iend = True
        elif kind[0] & 0x20 == 0:
            raise ValueError("Unsupported critical PNG chunk")
        if seen_idat and kind not in (b"IDAT", b"IEND"):
            idat_ended = True
        offset = end
        if seen_iend:
            break
    if not seen_iend or palette is None:
        raise ValueError("Incomplete Indexed PNG")
    with Image.open(io.BytesIO(payload)) as image:
        if image.format != "PNG" or image.mode != "P":
            raise ValueError("PNG decoder did not preserve palette indexes")
        image.load()
        if any(index >= len(palette) // 3 for index in image.tobytes()):
            raise ValueError("PNG pixel index exceeds PLTE")
    return tuple(
        (
            palette[index],
            palette[index + 1],
            palette[index + 2],
            alpha[index // 3] if index // 3 < len(alpha) else 255,
        )
        for index in range(0, len(palette), 3)
    )


def decode_palette_file(
    payload: bytes, file_format: Literal["gpl", "png"]
) -> PaletteFileFacts:
    try:
        if file_format == "gpl":
            entries = _gpl_entries(payload)
        elif file_format == "png":
            entries = _png_entries(payload)
        else:
            raise ValueError("Unsupported Palette file format")
        return PaletteFileFacts(
            entries, len(payload), hashlib.sha256(payload).hexdigest()
        )
    except (
        ValueError,
        UnicodeError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        raise PaletteFileError(str(exc)) from exc
