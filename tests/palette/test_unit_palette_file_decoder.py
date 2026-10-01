"""Independent observations of complete Palette file contents."""

import hashlib
import struct
import zlib

import pytest

from spa.adapters.palette_file import decode_palette_file
from spa.contracts.ports import PaletteFileError
from tests.palette.support import oversized_palette_png, png_chunk


def test_png_decoder_size_refusal_is_a_palette_file_error() -> None:
    with pytest.raises(PaletteFileError, match="decompression bomb"):
        decode_palette_file(oversized_palette_png(), "png")


def _png(
    colors: list[tuple[int, int, int]],
    pixels: bytes = b"\x00",
    *,
    alpha: bytes | None = None,
    color_type: int = 3,
    bit_depth: int = 8,
) -> bytes:
    header = struct.pack(">IIBBBBB", len(pixels), 1, bit_depth, color_type, 0, 0, 0)
    palette = bytes(channel for color in colors for channel in color)
    chunks = [png_chunk(b"IHDR", header), png_chunk(b"PLTE", palette)]
    if alpha is not None:
        chunks.append(png_chunk(b"tRNS", alpha))
    chunks.extend(
        (png_chunk(b"IDAT", zlib.compress(b"\x00" + pixels)), png_chunk(b"IEND", b""))
    )
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def test_indexed_png_preserves_unused_duplicates_and_short_alpha_table() -> None:
    payload = _png([(1, 2, 3), (4, 5, 6), (4, 5, 6)], b"\x01", alpha=b"\x00\x80")

    facts = decode_palette_file(payload, "png")

    assert facts.entries == ((1, 2, 3, 0), (4, 5, 6, 128), (4, 5, 6, 255))
    assert facts.byte_size == len(payload)
    assert facts.sha256 == hashlib.sha256(payload).hexdigest()


def test_indexed_png_without_trns_defaults_every_alpha_to_255() -> None:
    payload = _png([(7, 8, 9), (10, 11, 12)], b"\x00")

    assert decode_palette_file(payload, "png").entries == (
        (7, 8, 9, 255),
        (10, 11, 12, 255),
    )


def test_indexed_png_accepts_256_entries_and_packed_indexes() -> None:
    colors = [(index, 0, 255 - index) for index in range(256)]
    payload = _png(colors, b"\xff")

    facts = decode_palette_file(payload, "png")

    assert len(facts.entries) == 256
    assert facts.entries[255] == (255, 0, 0, 255)
    assert decode_palette_file(
        _png(colors[:2], b"\x80", bit_depth=1), "png"
    ).entries == (
        (0, 0, 255, 255),
        (1, 0, 254, 255),
    )


@pytest.mark.parametrize(
    "payload",
    [
        _png([(1, 2, 3)], b"\x01"),  # A real stored index has no PLTE entry.
        _png([], b"\x00"),
        _png([(index % 256, 0, 0) for index in range(257)]),
        _png([(1, 2, 3)], alpha=b"\x01\x02"),
        _png([(1, 2, 3)], color_type=2),
        _png([(1, 2, 3)], bit_depth=1, pixels=b"\x80"),
        _png([(1, 2, 3)])[:-12],  # Missing IEND.
        _png([(1, 2, 3)]) + b"after IEND",
    ],
)
def test_invalid_indexed_png_is_rejected(payload: bytes) -> None:
    with pytest.raises(PaletteFileError):
        decode_palette_file(payload, "png")


def test_indexed_png_rejects_bad_crc_and_corrupt_pixel_stream() -> None:
    valid = _png([(1, 2, 3)])
    bad_crc = bytearray(valid)
    bad_crc[41] ^= 1  # Alter the PLTE data without updating its CRC.
    bad_stream = (
        valid[:48]  # Signature, IHDR, and PLTE.
        + png_chunk(b"IDAT", zlib.compress(b"\x00"))
        + png_chunk(b"IEND", b"")
    )

    for payload in (bytes(bad_crc), bad_stream):
        with pytest.raises(PaletteFileError):
            decode_palette_file(payload, "png")


def test_gpl_preserves_rgb_and_extended_rgba_entries_without_size_limit() -> None:
    rgb = b"GIMP Palette\nName: swatch\n# comment\n1 2 3 first\n1 2 3 copy\n"
    rgba = b"GIMP Palette\nChannels: RGBA\n4 5 6 0 clear\n7 8 9 128 partial\n"
    large = b"GIMP Palette\n" + b"1 2 3 named\n" * 257

    assert decode_palette_file(rgb, "gpl").entries == ((1, 2, 3, 255),) * 2
    assert decode_palette_file(rgba, "gpl").entries == (
        (4, 5, 6, 0),
        (7, 8, 9, 128),
    )
    assert len(decode_palette_file(large, "gpl").entries) == 257


@pytest.mark.parametrize(
    "record",
    [
        b"Channels: CMYK\n1 2 3 4 named\n",
        b"Channels: RGBA\n1 2 3 missing-alpha\n",
        b"1 -2 3 negative\n",
        b"1 2 256 overflow\n",
        b"1 2 three malformed\n",
        b"Unknown: looks-like-metadata\n1 2 3 named\n",
        b"",
    ],
)
def test_gpl_rejects_invalid_color_payload(record: bytes) -> None:
    with pytest.raises(PaletteFileError):
        decode_palette_file(b"GIMP Palette\n" + record, "gpl")


def test_gpl_rejects_channel_switch_after_first_entry() -> None:
    payload = b"GIMP Palette\n1 2 3 first\nChannels: RGBA\n4 5 6 7 second\n"

    with pytest.raises(PaletteFileError):
        decode_palette_file(payload, "gpl")
