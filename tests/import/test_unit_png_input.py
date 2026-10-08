"""Encoded raster facts must preserve the complete source pixels."""

import struct
import zlib
from importlib.resources import files

import pytest
from PIL import ImageCms

from spa.adapters.png_input import decode_png_input
from spa.contracts.ports import PngInputError


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data))
    )


def _png(
    pixels: bytes,
    *,
    color_type: int = 6,
    bit_depth: int = 8,
    width: int = 1,
    height: int = 1,
    before: tuple[tuple[bytes, bytes], ...] = (),
    after: tuple[tuple[bytes, bytes], ...] = (),
    compressed: bytes | None = None,
    interlace: int = 0,
) -> bytes:
    header = struct.pack(
        ">IIBBBBB", width, height, bit_depth, color_type, 0, 0, interlace
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + b"".join(_chunk(*item) for item in before)
        + _chunk(b"IDAT", zlib.compress(pixels) if compressed is None else compressed)
        + b"".join(_chunk(*item) for item in after)
        + _chunk(b"IEND", b"")
    )


def test_rgba_preserves_hidden_rgb_and_partial_alpha() -> None:
    rgba = bytes((11, 22, 33, 0, 44, 55, 66, 128))

    facts = decode_png_input(_png(b"\x00" + rgba, width=2))

    assert (facts.width, facts.height, facts.color_mode) == (2, 1, "rgb")
    assert facts.rgba_bytes == facts.stored_bytes == rgba
    assert facts.entries == ()
    assert facts.color_profile == "none"
    assert facts.icc_bytes is None


def test_rgb_transparency_preserves_complete_hidden_color() -> None:
    facts = decode_png_input(
        _png(
            b"\x00\x0b\x16\x21\x2c\x37\x42",
            width=2,
            color_type=2,
            before=((b"tRNS", struct.pack(">HHH", 11, 22, 33)),),
        )
    )

    assert facts.rgba_bytes == bytes((11, 22, 33, 0, 44, 55, 66, 255))


def test_indexed_preserves_indexes_entries_and_partial_alpha() -> None:
    facts = decode_png_input(
        _png(
            b"\x00\x01\x00\x01",
            width=3,
            color_type=3,
            before=(
                (b"PLTE", bytes((1, 2, 3, 4, 5, 6, 7, 8, 9))),
                (b"tRNS", b"\x00\x80"),
            ),
        )
    )

    assert facts.color_mode == "indexed"
    assert facts.stored_bytes == b"\x01\x00\x01"
    assert facts.entries == ((1, 2, 3, 0), (4, 5, 6, 128), (7, 8, 9, 255))
    assert facts.rgba_bytes == bytes((4, 5, 6, 128, 1, 2, 3, 0, 4, 5, 6, 128))


@pytest.mark.parametrize(
    "color_type,bit_depth", [(2, 16), (6, 16), (3, 1), (3, 4), (0, 8), (4, 8)]
)
def test_unsupported_encoded_sample_representation_is_rejected(
    color_type: int, bit_depth: int
) -> None:
    with pytest.raises(PngInputError):
        decode_png_input(_png(b"\x00" * 9, color_type=color_type, bit_depth=bit_depth))


@pytest.mark.parametrize(
    "before,after",
    [
        (((b"acTL", struct.pack(">II", 1, 0)),), ()),
        ((), ((b"fdAT", b"\x00\x00\x00\x00"),)),
        (((b"PLTE", b"\x01\x02"),), ()),
        (((b"tRNS", b"\x00"),), ()),
        (((b"PLTE", b"\x01\x02\x03"), (b"tRNS", b"\x00"), (b"tRNS", b"\x00")), ()),
        ((), ((b"PLTE", b"\x01\x02\x03"),)),
        ((), ((b"sRGB", b"\x00"),)),
        (((b"sRGB", b"\x00"), (b"sRGB", b"\x00")), ()),
    ],
)
def test_invalid_structure_or_animation_is_rejected(
    before: tuple, after: tuple
) -> None:
    with pytest.raises(PngInputError):
        decode_png_input(_png(b"\x00\x01\x02\x03\x04", before=before, after=after))


@pytest.mark.parametrize(
    "palette,alpha,pixels",
    [
        (b"", None, b"\x00"),
        (b"\x01\x02\x03", b"", b"\x00"),
        (b"\x01\x02\x03", b"\x00\x80", b"\x00"),
        (b"\x01\x02\x03", None, b"\x01"),
    ],
)
def test_invalid_palette_or_undefined_used_index_is_rejected(
    palette: bytes, alpha: bytes | None, pixels: bytes
) -> None:
    before = ((b"PLTE", palette),)
    if alpha is not None:
        before += ((b"tRNS", alpha),)
    with pytest.raises(PngInputError):
        decode_png_input(_png(b"\x00" + pixels, color_type=3, before=before))


@pytest.mark.parametrize("name", ["linear_srgb", "display_p3_cc0"])
def test_valid_icc_preserves_exact_profile_bytes(name: str) -> None:
    profile = (
        files("spa.kernel").joinpath("color", "profiles", name + ".icc").read_bytes()
    )
    facts = decode_png_input(
        _png(
            b"\x00\x01\x02\x03\xff",
            before=((b"iCCP", b"profile\x00\x00" + zlib.compress(profile)),),
        )
    )
    assert facts.color_profile == "icc"
    assert facts.icc_bytes == profile


def test_srgb_accepts_consistent_standard_gamma_and_chromaticity() -> None:
    chunks = (
        (b"sRGB", b"\x00"),
        (b"gAMA", struct.pack(">I", 45455)),
        (
            b"cHRM",
            struct.pack(">8I", 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000),
        ),
    )
    facts = decode_png_input(_png(b"\x00\x01\x02\x03\xff", before=chunks))
    assert facts.color_profile == "srgb"
    assert facts.icc_bytes is None


@pytest.mark.parametrize(
    "chunks",
    [
        ((b"gAMA", struct.pack(">I", 45455)),),
        ((b"cHRM", b"\x00" * 32),),
        ((b"sRGB", b"\x04"),),
        ((b"sRGB", b"\x00\x00"),),
        ((b"sRGB", b"\x00"), (b"gAMA", struct.pack(">I", 100000))),
        ((b"sRGB", b"\x00"), (b"cHRM", b"\x00" * 32)),
        ((b"sRGB", b"\x00"), (b"iCCP", b"profile\x00\x00" + zlib.compress(b"invalid"))),
        ((b"cICP", b"\x01\x0d\x00\x01"),),
        ((b"mDCV", b"\x00" * 24),),
        ((b"cLLI", b"\x00" * 8),),
        ((b"eXIf", b"II\x2a\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00"),),
        ((b"iCCP", b"profile\x00\x01" + zlib.compress(b"invalid")),),
        ((b"iCCP", b" profile\x00\x00" + zlib.compress(b"invalid")),),
        ((b"iCCP", b"profile\x00\x00" + zlib.compress(b"invalid")),),
    ],
)
def test_unsupported_invalid_or_conflicting_color_metadata_is_rejected(
    chunks: tuple,
) -> None:
    with pytest.raises(PngInputError):
        decode_png_input(_png(b"\x00\x01\x02\x03\xff", before=chunks))


@pytest.mark.parametrize(
    "compressed",
    [
        zlib.compress(b"\x00\x01\x02\x03\xff")[:-1],
        zlib.compress(b"\x00\x01\x02\x03\xff") + b"extra",
        zlib.compress(b"\x00\x01\x02\x03\xff\x00"),
        zlib.compress(b"\x00\x01\x02\x03"),
        zlib.compress(b"\x05\x01\x02\x03\xff"),
    ],
)
def test_invalid_complete_pixel_stream_is_rejected(compressed: bytes) -> None:
    with pytest.raises(PngInputError):
        decode_png_input(_png(b"", compressed=compressed))


def test_adam7_preserves_complete_rgba_pixels() -> None:
    first = bytes((1, 2, 3, 0))
    second = bytes((4, 5, 6, 128))
    third = bytes((7, 8, 9, 255))
    fourth = bytes((10, 11, 12, 255))
    # A 2x2 Adam7 image has nonempty passes 1, 6, and 7.
    pixels = b"\x00" + first + b"\x00" + second + b"\x00" + third + fourth
    facts = decode_png_input(_png(pixels, width=2, height=2, interlace=1))
    assert facts.rgba_bytes == first + second + third + fourth


def test_consecutive_idat_chunks_form_one_complete_pixel_stream() -> None:
    payload = _png(b"\x00\x01\x02\x03\xff")
    compressed = zlib.compress(b"\x00\x01\x02\x03\xff")
    split = (
        payload[:33]
        + _chunk(b"IDAT", compressed[:5])
        + _chunk(b"IDAT", compressed[5:])
        + payload[-12:]
    )
    assert decode_png_input(split).rgba_bytes == b"\x01\x02\x03\xff"
    separated = (
        payload[:33]
        + _chunk(b"IDAT", compressed[:5])
        + _chunk(b"tEXt", b"key\x00value")
        + _chunk(b"IDAT", compressed[5:])
        + payload[-12:]
    )
    with pytest.raises(PngInputError, match="Nonconsecutive"):
        decode_png_input(separated)


def test_crc_signature_complete_chunk_and_iend_validation() -> None:
    valid = _png(b"\x00\x01\x02\x03\xff")
    bad_crc = bytearray(valid)
    bad_crc[45] ^= 1
    for payload in (
        b"not a PNG",
        valid[:-12],
        valid + b"extra",
        valid[:40],
        bytes(bad_crc),
    ):
        with pytest.raises(PngInputError):
            decode_png_input(payload)


def test_png_size_refusal_is_a_png_input_error() -> None:
    payload = _png(b"", width=0x7FFFFFFF, height=0x7FFFFFFF)
    with pytest.raises(PngInputError, match="decompression bomb"):
        decode_png_input(payload)


def test_valid_rgb_ignores_optional_suggested_palette_and_keeps_opaque_alpha() -> None:
    facts = decode_png_input(
        _png(b"\x00\x01\x02\x03", color_type=2, before=((b"PLTE", b"\x04\x05\x06"),))
    )
    assert facts.rgba_bytes == facts.stored_bytes == b"\x01\x02\x03\xff"
    assert facts.entries == ()


def test_indexed_without_trns_preserves_opaque_index_zero() -> None:
    facts = decode_png_input(
        _png(b"\x00\x00", color_type=3, before=((b"PLTE", b"\x04\x05\x06"),))
    )
    assert facts.stored_bytes == b"\x00"
    assert facts.rgba_bytes == b"\x04\x05\x06\xff"
    assert facts.entries == ((4, 5, 6, 255),)


@pytest.mark.parametrize("profile_kind", ["sRGB", "LAB"])
def test_decoder_does_not_define_application_supported_icc_set(
    profile_kind: str,
) -> None:
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile(profile_kind)).tobytes()
    payload = _png(
        b"\x00\x01\x02\x03\xff",
        before=((b"iCCP", b"other\x00\x00" + zlib.compress(profile)),),
    )
    if profile_kind == "sRGB":
        facts = decode_png_input(payload)
        assert facts.color_profile == "icc"
        assert facts.icc_bytes == profile
    else:
        with pytest.raises(PngInputError, match="must describe RGB"):
            decode_png_input(payload)


def test_icc_with_fallback_color_definitions_is_an_unsupported_combination() -> None:
    profile = (
        files("spa.kernel")
        .joinpath("color", "profiles", "linear_srgb.icc")
        .read_bytes()
    )
    chunks = (
        (b"iCCP", b"profile\x00\x00" + zlib.compress(profile)),
        (b"gAMA", struct.pack(">I", 100000)),
    )
    with pytest.raises(PngInputError, match="Unsupported.*combination"):
        decode_png_input(_png(b"\x00\x01\x02\x03\xff", before=chunks))
