"""Independent observations of encoded animation delivery bytes."""

import struct
import zlib
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from spa.adapters.gif import decode_gif
from spa.adapters.sequence_png import decode_sequence_png
from spa.contracts.encoded_animation import AnimationDecodeError


def _png(image: Image.Image, **options: object) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", **options)
    return output.getvalue()


def test_sequence_png_observes_rgb_samples_and_alpha() -> None:
    image = Image.new("RGBA", (2, 1))
    image.putdata([(11, 22, 33, 0), (44, 55, 66, 127)])

    decoded = decode_sequence_png(_png(image))

    assert (decoded.width, decoded.height) == (2, 1)
    assert decoded.color_mode == "rgb"
    assert decoded.color_type == 6 and decoded.bit_depth == 8
    assert decoded.stored_bytes == bytes([11, 22, 33, 0, 44, 55, 66, 127])
    assert decoded.rgba_bytes == decoded.stored_bytes
    assert decoded.entries == ()
    assert decoded.color_profile == "none"
    assert decoded.icc_bytes is None and decoded.srgb_rendering_intent is None


def test_sequence_png_preserves_grayscale_samples_and_alpha() -> None:
    image = Image.new("LA", (2, 1))
    image.putdata([(37, 0), (183, 91)])

    decoded = decode_sequence_png(_png(image))

    assert decoded.color_mode == "grayscale"
    assert decoded.color_type == 4 and decoded.bit_depth == 8
    assert decoded.stored_bytes == bytes([37, 0, 183, 91])
    assert decoded.rgba_bytes == bytes([37, 37, 37, 0, 183, 183, 183, 91])
    assert decoded.entries == ()


@pytest.mark.parametrize("depth", [1, 2, 4, 8])
def test_sequence_png_preserves_indexed_palette_and_unpacked_indexes(
    depth: int,
) -> None:
    image = Image.new("P", (3, 1))
    image.putpalette([9, 19, 29, 9, 19, 29])
    image.putdata([1, 0, 1])

    decoded = decode_sequence_png(_png(image, bits=depth, transparency=bytes([0, 87])))

    assert decoded.color_mode == "indexed"
    assert decoded.color_type == 3 and decoded.bit_depth == depth
    assert decoded.stored_bytes == bytes([1, 0, 1])
    assert decoded.entries[:2] == ((9, 19, 29, 0), (9, 19, 29, 87))
    assert len(decoded.entries) == 2**depth
    assert decoded.entries[2:] == ((0, 0, 0, 255),) * (2**depth - 2)
    assert decoded.rgba_bytes == bytes([9, 19, 29, 87, 9, 19, 29, 0, 9, 19, 29, 87])


@pytest.mark.parametrize(
    "mode,transparent,expected",
    [
        ("L", 37, bytes([37, 0, 183, 255])),
        ("RGB", (37, 37, 37), bytes([37, 37, 37, 0, 183, 183, 183, 255])),
    ],
)
def test_sequence_png_observes_transparency_without_an_alpha_channel(
    mode: str,
    transparent: object,
    expected: bytes,
) -> None:
    image = Image.new(mode, (2, 1))
    image.putdata([37, 183] if mode == "L" else [(37, 37, 37), (183, 183, 183)])

    decoded = decode_sequence_png(_png(image, transparency=transparent))

    assert decoded.stored_bytes == expected


def test_sequence_png_reports_srgb_rendering_intent() -> None:
    info = PngInfo()
    info.add(b"sRGB", bytes([3]))

    decoded = decode_sequence_png(_png(Image.new("LA", (1, 1)), pnginfo=info))

    assert decoded.color_profile == "srgb"
    assert decoded.srgb_rendering_intent == 3
    assert decoded.icc_bytes is None


@pytest.mark.parametrize("mode", ["RGB", "P"])
def test_sequence_png_reports_exact_icc_payload(mode: str) -> None:
    profile = Path("src/spa/kernel/color/profiles/display_p3.icc").read_bytes()
    image = Image.new(mode, (1, 1))
    if mode == "P":
        image.putpalette([11, 22, 33])

    decoded = decode_sequence_png(_png(image, icc_profile=profile))

    assert decoded.color_profile == "icc"
    assert decoded.icc_bytes == profile
    assert decoded.srgb_rendering_intent is None


def _replace_png_chunk(payload: bytes, kind: bytes, data: bytes) -> bytes:
    offset = payload.index(kind) - 4
    size = struct.unpack_from(">I", payload, offset)[0]
    chunk = (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data))
    )
    return payload[:offset] + chunk + payload[offset + size + 12 :]


@pytest.mark.parametrize(
    "damage",
    ["crc", "trailing", "truncated", "scanline", "zlib_tail", "duplicate_ihdr"],
)
def test_sequence_png_rejects_incomplete_or_inconsistent_encoded_bytes(
    damage: str,
) -> None:
    payload = _png(Image.new("RGBA", (2, 1)))
    if damage == "crc":
        payload = payload[:29] + bytes([payload[29] ^ 1]) + payload[30:]
    elif damage == "trailing":
        payload += b"extra"
    elif damage == "truncated":
        payload = payload[:-2]
    elif damage == "scanline":
        payload = _replace_png_chunk(payload, b"IDAT", zlib.compress(bytes([0]) * 8))
    elif damage == "zlib_tail":
        offset = payload.index(b"IDAT")
        size = struct.unpack_from(">I", payload, offset - 4)[0]
        payload = _replace_png_chunk(
            payload, b"IDAT", payload[offset + 4 : offset + 4 + size] + b"tail"
        )
    else:
        payload = payload[:33] + payload[8:33] + payload[33:]

    with pytest.raises(AnimationDecodeError):
        decode_sequence_png(payload)


def test_sequence_png_rejects_pixel_index_without_palette_entry() -> None:
    image = Image.new("P", (1, 1), 2)
    image.putpalette([11, 22, 33, 44, 55, 66, 77, 88, 99])
    payload = _replace_png_chunk(
        _png(image, bits=8), b"PLTE", bytes([11, 22, 33, 44, 55, 66])
    )

    with pytest.raises(AnimationDecodeError, match="pixel index exceeds PLTE"):
        decode_sequence_png(payload)


def _gif(*, loop: int | None = 0, transparency: int | None = 0) -> bytes:
    palette = [0, 0, 0, 201, 11, 21, 31, 191, 41, 51, 61, 181]
    frames = []
    for index in (1, 2, 3):
        image = Image.new("P", (2, 1))
        image.putpalette(palette)
        image.putdata([0, index])
        frames.append(image)
    output = BytesIO()
    options: dict[str, object] = {}
    if loop is not None:
        options["loop"] = loop
    if transparency is not None:
        options["transparency"] = transparency
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[20, 30, 40],
        disposal=2,
        optimize=False,
        **options,
    )
    return output.getvalue()


def test_gif_observes_every_logical_screen_frame_duration_loop_and_color_table() -> (
    None
):
    decoded = decode_gif(_gif())

    assert (decoded.width, decoded.height) == (2, 1)
    assert decoded.loop_count == 0
    assert [frame.duration_ms for frame in decoded.frames] == [20, 30, 40]
    assert [frame.rgba_bytes for frame in decoded.frames] == [
        bytes([0, 0, 0, 0, 201, 11, 21, 255]),
        bytes([0, 0, 0, 0, 31, 191, 41, 255]),
        bytes([0, 0, 0, 0, 51, 61, 181, 255]),
    ]
    assert all(frame.transparent_color_index == 0 for frame in decoded.frames)
    assert all(frame.disposal_method == 2 for frame in decoded.frames)
    assert [frame.rectangle for frame in decoded.frames] == [
        (0, 0, 2, 1),
        (1, 0, 1, 1),
        (1, 0, 1, 1),
    ]
    assert decoded.frames[0].color_table_source == "global"
    assert decoded.frames[1].color_table_source == "local"
    assert decoded.global_color_table[:4] == (
        (0, 0, 0),
        (201, 11, 21),
        (31, 191, 41),
        (51, 61, 181),
    )
    assert all(
        frame.color_table == decoded.global_color_table for frame in decoded.frames
    )


@pytest.mark.parametrize("loop", [None, 7])
def test_gif_reports_absent_or_finite_loop_without_reinterpreting_it(
    loop: int | None,
) -> None:
    assert decode_gif(_gif(loop=loop)).loop_count == loop


def test_gif_observes_single_frame_without_graphics_control() -> None:
    output = BytesIO()
    Image.new("RGB", (1, 1), (20, 30, 40)).save(output, format="GIF")

    decoded = decode_gif(output.getvalue())

    assert decoded.loop_count is None
    assert len(decoded.frames) == 1
    assert decoded.frames[0].duration_ms == 0
    assert decoded.frames[0].transparent_color_index is None
    assert decoded.frames[0].disposal_method == 0
    assert decoded.frames[0].rgba_bytes == bytes([20, 30, 40, 255])


def test_gif_observes_distinct_local_palette_and_disposal_composition() -> None:
    first = Image.new("P", (2, 1), 1)
    first.putpalette([0, 0, 0, 200, 10, 20])
    second = Image.new("P", (2, 1), 1)
    second.putpalette([0, 0, 0, 10, 20, 200])
    output = BytesIO()
    first.save(
        output,
        format="GIF",
        save_all=True,
        append_images=[second],
        duration=[10, 20],
        disposal=1,
        optimize=False,
    )

    decoded = decode_gif(output.getvalue())

    assert [frame.rgba_bytes for frame in decoded.frames] == [
        bytes([200, 10, 20, 255]) * 2,
        bytes([10, 20, 200, 255]) * 2,
    ]
    assert decoded.frames[0].color_table[1] == (200, 10, 20)
    assert decoded.frames[1].color_table[1] == (10, 20, 200)
    assert decoded.frames[1].color_table_source == "local"
    assert all(frame.disposal_method == 1 for frame in decoded.frames)


@pytest.mark.parametrize(
    "damage",
    [
        "missing_trailer",
        "truncated_table",
        "truncated_data",
        "trailing",
        "background_index",
        "gce_size",
        "gce_flags",
        "transparent_index",
        "gce_terminator",
        "loop_marker",
        "duplicate_loop",
        "out_of_canvas",
        "lzw_size",
    ],
)
def test_gif_rejects_incomplete_or_invalid_blocks(damage: str) -> None:
    payload = bytearray(_gif())
    gce = payload.index(b"\x21\xf9\x04")
    image = payload.index(b"\x2c", gce)
    loop = payload.index(b"NETSCAPE2.0")
    if damage == "missing_trailer":
        payload = payload[:-1]
    elif damage == "truncated_table":
        payload = payload[:20]
    elif damage == "truncated_data":
        payload = payload[:-3]
    elif damage == "trailing":
        payload += b"extra"
    elif damage == "background_index":
        payload[11] = 255
    elif damage == "gce_size":
        payload[gce + 2] = 3
    elif damage == "gce_flags":
        payload[gce + 3] |= 0x80
    elif damage == "transparent_index":
        payload[gce + 6] = 255
    elif damage == "gce_terminator":
        payload[gce + 7] = 1
    elif damage == "loop_marker":
        payload[loop + 12] = 2
    elif damage == "duplicate_loop":
        payload = payload[:gce] + payload[loop - 3 : loop + 16] + payload[gce:]
    elif damage == "out_of_canvas":
        payload[image + 5 : image + 7] = struct.pack("<H", 3)
    else:
        payload[image + 10] = 1

    with pytest.raises(AnimationDecodeError):
        decode_gif(bytes(payload))


def test_gif_reports_encoded_application_extension_bytes() -> None:
    payload = _gif()
    position = payload.index(b"\x21\xf9\x04")
    # An unknown application identifier is observation data, not a support policy.
    extension = b"\x21\xff\x0bICCRGBG1012\x03abc\x00"

    decoded = decode_gif(payload[:position] + extension + payload[position:])

    assert (b"ICCRGBG1012", b"abc") in decoded.application_extensions


def test_gif_keeps_blank_final_frame_as_a_full_logical_screen_occurrence() -> None:
    first = Image.new("P", (2, 1), 1)
    first.putpalette([0, 0, 0, 200, 10, 20])
    blank = Image.new("P", (2, 1))
    blank.putpalette([0, 0, 0, 200, 10, 20])
    output = BytesIO()
    first.save(
        output,
        format="GIF",
        save_all=True,
        append_images=[blank],
        transparency=0,
        duration=[10, 30],
        disposal=3,
        optimize=False,
    )

    decoded = decode_gif(output.getvalue())

    assert len(decoded.frames) == 2
    assert decoded.frames[1].duration_ms == 30
    assert decoded.frames[1].rgba_bytes == bytes([0, 0, 0, 0]) * 2
