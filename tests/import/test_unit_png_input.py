"""Encoded raster facts must preserve the complete source pixels."""

import struct
import zlib
from importlib.resources import files

import pytest
from PIL import ImageCms

from spa.adapters.png_input import decode_png_artifact, decode_png_input
from spa.adapters.sequence_png import decode_sequence_png
from spa.contracts.encoded_animation import AnimationDecodeError
from spa.contracts.ports import PngInputError


@pytest.fixture(
    params=[
        (decode_png_input, PngInputError),
        (decode_png_artifact, PngInputError),
        (decode_sequence_png, AnimationDecodeError),
    ],
    ids=["input", "artifact", "sequence"],
)
def png_decoder(request):
    return request.param


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


def test_rgba_preserves_hidden_rgb_and_partial_alpha(png_decoder) -> None:
    decode, _error = png_decoder
    rgba = bytes((11, 22, 33, 0, 44, 55, 66, 128))

    facts = decode(_png(b"\x00" + rgba, width=2))

    assert (facts.width, facts.height, facts.color_mode) == (2, 1, "rgb")
    assert facts.rgba_bytes == facts.stored_bytes == rgba
    assert facts.entries == ()
    assert facts.color_profile == "none"
    assert facts.icc_bytes is None


def test_rgb_transparency_preserves_complete_hidden_color(png_decoder) -> None:
    decode, _error = png_decoder
    facts = decode(
        _png(
            b"\x00\x0b\x16\x21\x2c\x37\x42",
            width=2,
            color_type=2,
            before=((b"tRNS", struct.pack(">HHH", 11, 22, 33)),),
        )
    )

    assert facts.rgba_bytes == bytes((11, 22, 33, 0, 44, 55, 66, 255))


@pytest.mark.parametrize("decode", [decode_png_artifact, decode_sequence_png])
@pytest.mark.parametrize("transparent", [False, True])
def test_grayscale_output_observes_trns_without_losing_hidden_sample(
    decode, transparent: bool
) -> None:
    # PNG section 11.3.1.1 defines a two-byte transparent sample for type 0.
    before = ((b"tRNS", b"\x00\x25"),) if transparent else ()
    facts = decode(_png(b"\x00\x25", color_type=0, before=before))

    alpha = 0 if transparent else 255
    assert facts.color_mode == "grayscale" and facts.color_type == 0
    assert facts.rgba_bytes == bytes((37, 37, 37, alpha))
    assert facts.stored_bytes == bytes((37, alpha))
    assert facts.entries == ()


def test_indexed_preserves_indexes_entries_and_partial_alpha(png_decoder) -> None:
    decode, _error = png_decoder
    facts = decode(
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
    "color_type,depth,pixels,admitted",
    [
        (0, 8, b"\x00\x25", (decode_png_artifact, decode_sequence_png)),
        (4, 8, b"\x00\x25\x7f", (decode_png_artifact, decode_sequence_png)),
        (3, 1, b"\x00\x80", (decode_sequence_png,)),
        (3, 2, b"\x00\x40", (decode_sequence_png,)),
        (3, 4, b"\x00\x10", (decode_sequence_png,)),
        (0, 16, b"\x00\x00\x25", ()),
        (2, 16, b"\x00\x00\x25\x00\x25\x00\x25", ()),
    ],
)
def test_entry_points_preserve_their_representation_subsets(
    png_decoder, color_type, depth, pixels, admitted
) -> None:
    decode, error = png_decoder
    before = ((b"PLTE", bytes((1, 2, 3, 4, 5, 6))),) if color_type == 3 else ()
    payload = _png(pixels, color_type=color_type, bit_depth=depth, before=before)

    if decode in admitted:
        facts = decode(payload)
        assert (facts.width, facts.height, facts.color_type) == (1, 1, color_type)
        if color_type == 3:
            assert facts.stored_bytes == b"\x01"
            assert facts.rgba_bytes == b"\x04\x05\x06\xff"
        else:
            expected_alpha = 127 if color_type == 4 else 255
            assert facts.stored_bytes == bytes((37, expected_alpha))
            assert facts.rgba_bytes == bytes((37, 37, 37, expected_alpha))
    else:
        message = "Palette Indexes" if decode == decode_sequence_png else "8-bit subset"
        with pytest.raises(error, match=message):
            decode(payload)


@pytest.mark.parametrize(
    "decode,error",
    [(decode_png_artifact, PngInputError), (decode_sequence_png, AnimationDecodeError)],
)
@pytest.mark.parametrize(
    "color_type,alpha", [(0, b""), (0, b"\x25"), (0, b"\x01\x00"), (4, b"\x00\x25")]
)
def test_grayscale_output_retains_transparency_refusals(
    decode, error, color_type, alpha
) -> None:
    pixels = b"\x00\x25" if color_type == 0 else b"\x00\x25\xff"
    payload = _png(pixels, color_type=color_type, before=((b"tRNS", alpha),))
    with pytest.raises(error, match="Invalid Grayscale PNG tRNS"):
        decode(payload)


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
    png_decoder, before: tuple, after: tuple
) -> None:
    decode, error = png_decoder
    with pytest.raises(error):
        decode(_png(b"\x00\x01\x02\x03\x04", before=before, after=after))


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
    png_decoder, palette: bytes, alpha: bytes | None, pixels: bytes
) -> None:
    decode, error = png_decoder
    before = ((b"PLTE", palette),)
    if alpha is not None:
        before += ((b"tRNS", alpha),)
    with pytest.raises(error):
        decode(_png(b"\x00" + pixels, color_type=3, before=before))


@pytest.mark.parametrize(
    "decode,error",
    [(decode_png_artifact, PngInputError), (decode_sequence_png, AnimationDecodeError)],
)
@pytest.mark.parametrize("color_type", [0, 4])
def test_grayscale_output_rejects_forbidden_palette(decode, error, color_type) -> None:
    # PNG section 11.2.2 forbids PLTE for both Grayscale representations.
    pixels = b"\x00\x25" if color_type == 0 else b"\x00\x25\xff"
    payload = _png(pixels, color_type=color_type, before=((b"PLTE", b"\x01\x02\x03"),))

    with pytest.raises(error, match="Grayscale PNG cannot contain PLTE"):
        decode(payload)


@pytest.mark.parametrize("name", ["linear_srgb", "display_p3_cc0"])
def test_valid_icc_preserves_exact_profile_bytes(png_decoder, name: str) -> None:
    decode, _error = png_decoder
    profile = (
        files("spa.kernel").joinpath("color", "profiles", name + ".icc").read_bytes()
    )
    facts = decode(
        _png(
            b"\x00\x01\x02\x03\xff",
            before=((b"iCCP", b"profile\x00\x00" + zlib.compress(profile)),),
        )
    )
    assert facts.color_profile == "icc"
    assert facts.icc_bytes == profile


def test_srgb_accepts_consistent_standard_gamma_and_chromaticity(png_decoder) -> None:
    decode, _error = png_decoder
    chunks = (
        (b"sRGB", b"\x00"),
        (b"gAMA", struct.pack(">I", 45455)),
        (
            b"cHRM",
            struct.pack(">8I", 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000),
        ),
    )
    facts = decode(_png(b"\x00\x01\x02\x03\xff", before=chunks))
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
    png_decoder,
    chunks: tuple,
) -> None:
    decode, error = png_decoder
    with pytest.raises(error):
        decode(_png(b"\x00\x01\x02\x03\xff", before=chunks))


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
def test_invalid_complete_pixel_stream_is_rejected(
    png_decoder, compressed: bytes
) -> None:
    decode, error = png_decoder
    with pytest.raises(error):
        decode(_png(b"", compressed=compressed))


def test_adam7_preserves_complete_rgba_pixels(png_decoder) -> None:
    decode, _error = png_decoder
    first = bytes((1, 2, 3, 0))
    second = bytes((4, 5, 6, 128))
    third = bytes((7, 8, 9, 255))
    fourth = bytes((10, 11, 12, 255))
    # A 2x2 Adam7 image has nonempty passes 1, 6, and 7.
    pixels = b"\x00" + first + b"\x00" + second + b"\x00" + third + fourth
    facts = decode(_png(pixels, width=2, height=2, interlace=1))
    assert facts.rgba_bytes == first + second + third + fourth


def test_consecutive_idat_chunks_form_one_complete_pixel_stream(png_decoder) -> None:
    decode, error = png_decoder
    payload = _png(b"\x00\x01\x02\x03\xff")
    compressed = zlib.compress(b"\x00\x01\x02\x03\xff")
    split = (
        payload[:33]
        + _chunk(b"IDAT", compressed[:5])
        + _chunk(b"IDAT", compressed[5:])
        + payload[-12:]
    )
    assert decode(split).rgba_bytes == b"\x01\x02\x03\xff"
    separated = (
        payload[:33]
        + _chunk(b"IDAT", compressed[:5])
        + _chunk(b"tEXt", b"key\x00value")
        + _chunk(b"IDAT", compressed[5:])
        + payload[-12:]
    )
    with pytest.raises(error, match="Nonconsecutive"):
        decode(separated)


def test_crc_signature_complete_chunk_and_iend_validation(png_decoder) -> None:
    decode, error = png_decoder
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
        with pytest.raises(error):
            decode(payload)


def test_png_size_refusal_is_a_png_input_error(png_decoder) -> None:
    decode, error = png_decoder
    payload = _png(b"", width=0x7FFFFFFF, height=0x7FFFFFFF)
    with pytest.raises(error, match="decompression bomb"):
        decode(payload)


def test_valid_rgb_ignores_optional_suggested_palette_and_keeps_opaque_alpha(
    png_decoder,
) -> None:
    decode, _error = png_decoder
    facts = decode(
        _png(b"\x00\x01\x02\x03", color_type=2, before=((b"PLTE", b"\x04\x05\x06"),))
    )
    assert facts.rgba_bytes == facts.stored_bytes == b"\x01\x02\x03\xff"
    assert facts.entries == ()


def test_indexed_without_trns_preserves_opaque_index_zero(png_decoder) -> None:
    decode, _error = png_decoder
    facts = decode(
        _png(b"\x00\x00", color_type=3, before=((b"PLTE", b"\x04\x05\x06"),))
    )
    assert facts.stored_bytes == b"\x00"
    assert facts.rgba_bytes == b"\x04\x05\x06\xff"
    assert facts.entries == ((4, 5, 6, 255),)


@pytest.mark.parametrize("profile_kind", ["sRGB", "LAB"])
def test_decoder_does_not_define_application_supported_icc_set(
    png_decoder,
    profile_kind: str,
) -> None:
    decode, error = png_decoder
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile(profile_kind)).tobytes()
    payload = _png(
        b"\x00\x01\x02\x03\xff",
        before=((b"iCCP", b"other\x00\x00" + zlib.compress(profile)),),
    )
    if profile_kind == "sRGB":
        facts = decode(payload)
        assert facts.color_profile == "icc"
        assert facts.icc_bytes == profile
    else:
        with pytest.raises(error, match="must describe RGB"):
            decode(payload)


def test_icc_with_fallback_color_definitions_is_an_unsupported_combination(
    png_decoder,
) -> None:
    decode, error = png_decoder
    profile = (
        files("spa.kernel")
        .joinpath("color", "profiles", "linear_srgb.icc")
        .read_bytes()
    )
    chunks = (
        (b"iCCP", b"profile\x00\x00" + zlib.compress(profile)),
        (b"gAMA", struct.pack(">I", 100000)),
    )
    with pytest.raises(error, match="Unsupported.*combination"):
        decode(_png(b"\x00\x01\x02\x03\xff", before=chunks))
