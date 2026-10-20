"""Crop and canvas-resize through the CLI, with persisted pixel observations."""

from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.image.support import inspect_native
from tests.native_invocation import expect_success, render_frame, run
from tests.support import image_fixture, inject_palette_change

pytestmark = pytest.mark.e2e


def transform_request(source: Path, output: Path, **options) -> dict:
    """Return an Image crop or canvas-resize request for Layer 1, Frame 1.

    The request writes output, not in place and without overwrite, in
    `image-pixel` coordinates. Each option replaces one field.
    """
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(output),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        **options,
    }


def assert_persisted_link(source: Path) -> None:
    """Check that the Frame 2 Cel of Layer 1 in source links to Frame 1."""
    result = expect_success(
        "cel get",
        {
            "sprite_file": str(source),
            "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
        },
    )
    assert result["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 1}]


def test_crop_preserves_canvas_pixels_and_linked_cels(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = image_fixture(runtime, tmp_path, "linked")
    original = source.read_bytes()
    target = tmp_path / "crop.aseprite"

    result = expect_success(
        "image crop",
        transform_request(
            source,
            target,
            rectangle={"x": 1, "y": 0, "width": 1, "height": 2},
            position_policy="preserve_canvas_pixels",
        ),
    )
    assert source.read_bytes() == original
    assert result["copied_source_rectangle"] == {
        "x": 1,
        "y": 0,
        "width": 1,
        "height": 2,
    }
    assert result["copied_target_rectangle"] == {
        "x": 0,
        "y": 0,
        "width": 1,
        "height": 2,
    }
    assert result["discarded_source_regions"] == [
        {"x": 0, "y": 0, "width": 1, "height": 2}
    ]
    assert result["uncovered_target_regions"] == []
    assert result["position_delta"] == {"x": 1, "y": 0}
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1, 2]
    for cel in result["affected_cels"]:
        assert cel["before_position"] == {"x": 1, "y": 2}
        assert cel["after_position"] == {"x": 2, "y": 2}
        assert cel["after_image_bounds"] == {"width": 1, "height": 2}
    assert result["native_sharing_preserved"] is True
    assert_persisted_link(target)
    assert result["persisted_reopen_verified"] is True
    for frame in (1, 2):
        png = render_frame(target, frame)
        assert png.getpixel((2, 2)) == (0, 0, 255, 255)
        assert png.getpixel((1, 2))[3] == 0
        stored = inspect_native(runtime, target, tmp_path, 0, 0, frame)
        assert stored["width"] == 1
        assert stored["height"] == 2


def test_canvas_resize_clips_and_fills_without_moving_copied_canvas_pixels(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = image_fixture(runtime, tmp_path, "linked")
    target = tmp_path / "canvas.aseprite"
    result = expect_success(
        "image canvas-resize",
        transform_request(
            source,
            target,
            width=3,
            height=3,
            offset={"x": -1, "y": 1},
            fill={"kind": "rgba", "red": 0, "green": 255, "blue": 0, "alpha": 255},
            position_policy="preserve_source_canvas",
        ),
    )
    assert result["copied_source_rectangle"] == {
        "x": 1,
        "y": 0,
        "width": 1,
        "height": 2,
    }
    assert result["copied_target_rectangle"] == {
        "x": 0,
        "y": 1,
        "width": 1,
        "height": 2,
    }
    assert result["discarded_source_regions"] == [
        {"x": 0, "y": 0, "width": 1, "height": 2}
    ]
    assert result["uncovered_target_regions"] == [
        {"x": 0, "y": 0, "width": 3, "height": 1},
        {"x": 1, "y": 1, "width": 2, "height": 2},
    ]
    assert result["position_delta"] == {"x": 1, "y": -1}
    for cel in result["affected_cels"]:
        assert cel["after_position"] == {"x": 2, "y": 1}
    assert len(result["affected_cels"]) == 2
    assert result["native_sharing_preserved"] is True
    assert_persisted_link(target)
    for frame in (1, 2):
        png = render_frame(target, frame)
        assert png.getpixel((2, 2)) == (0, 0, 255, 255)
        assert png.getpixel((2, 1)) == (0, 255, 0, 255)
        # Transparent stored source pixels replace fill; this is not compositing.
        assert png.getpixel((2, 3))[3] == 0


def test_fill_index_must_exist_in_every_sharing_frame_palette(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = image_fixture(runtime, tmp_path, "indexed-linked")
    # Frame 1 has four entries. Frame 2 changes to only three entries.
    inject_palette_change(source, [(0, 0, 0, 0), (255, 0, 0, 255), (0, 0, 255, 255)])
    original = source.read_bytes()
    assert_persisted_link(source)
    outcome = run(
        "image canvas-resize",
        transform_request(
            source,
            source,
            width=3,
            height=3,
            offset={"x": 0, "y": 0},
            fill={"kind": "palette-index", "index": 3},
            position_policy="keep_cel_position",
            in_place=True,
            overwrite=True,
        ),
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "image_canvas_fill_invalid"
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("mode", "fill", "source_pixel", "fill_pixel"),
    [
        (
            "rgb-hidden",
            {"kind": "rgba", "red": 50, "green": 60, "blue": 70, "alpha": 0},
            {"red": 17, "green": 29, "blue": 41, "alpha": 0},
            {"red": 50, "green": 60, "blue": 70, "alpha": 0},
        ),
        (
            "grayscale-hidden",
            {"kind": "grayscale", "gray": 99, "alpha": 0},
            {"gray": 73, "alpha": 0},
            {"gray": 99, "alpha": 0},
        ),
        (
            "indexed-offset-mask",
            {"kind": "palette-index", "index": 2},
            {"pixel": 2, "transparent_index": 2},
            {"pixel": 2, "transparent_index": 2},
        ),
    ],
)
def test_transforms_keep_native_transparency_and_hidden_channels(
    tmp_path: Path,
    runtime: RuntimeObservation,
    mode: str,
    fill: dict,
    source_pixel: dict,
    fill_pixel: dict,
) -> None:
    source = image_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    crop = tmp_path / "single-pixel.aseprite"
    cropped = expect_success(
        "image crop",
        transform_request(
            source,
            crop,
            rectangle={"x": 1, "y": 1, "width": 1, "height": 1},
            position_policy="keep_cel_position",
        ),
    )
    assert cropped["affected_cels"][0]["after_position"] == {"x": 1, "y": 2}
    pixel = inspect_native(runtime, crop, tmp_path, 0, 0)
    assert {key: pixel[key] for key in source_pixel} == source_pixel

    canvas = tmp_path / "padded.aseprite"
    padded = expect_success(
        "image canvas-resize",
        transform_request(
            source,
            canvas,
            width=4,
            height=4,
            offset={"x": 1, "y": 1},
            fill=fill,
            position_policy="keep_cel_position",
        ),
    )
    assert padded["discarded_source_regions"] == []
    assert padded["affected_cels"][0]["after_position"] == {"x": 1, "y": 2}
    pixel = inspect_native(runtime, canvas, tmp_path, 2, 2)
    assert {key: pixel[key] for key in source_pixel} == source_pixel
    pixel = inspect_native(runtime, canvas, tmp_path, 0, 0)
    assert {key: pixel[key] for key in fill_pixel} == fill_pixel
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "offset", [{"x": 3, "y": 0}, {"x": -2, "y": 0}, {"x": 0, "y": 2}]
)
@pytest.mark.parametrize(
    ("mode", "fill", "expected"),
    [
        (
            "rgb",
            {"kind": "rgba", "red": 9, "green": 8, "blue": 7, "alpha": 255},
            {"red": 9, "green": 8, "blue": 7, "alpha": 255},
        ),
        (
            "grayscale",
            {"kind": "grayscale", "gray": 90, "alpha": 128},
            {"gray": 90, "alpha": 128},
        ),
        (
            "indexed-offset-mask",
            {"kind": "palette-index", "index": 2},
            {"pixel": 2, "transparent_index": 2},
        ),
    ],
)
def test_no_intersection_is_a_persisted_fill_only_image(
    tmp_path: Path,
    runtime: RuntimeObservation,
    mode: str,
    fill: dict,
    expected: dict,
    offset: dict,
) -> None:
    source = image_fixture(runtime, tmp_path, mode)
    target = tmp_path / "fill-only.aseprite"
    result = expect_success(
        "image canvas-resize",
        transform_request(
            source,
            target,
            width=3,
            height=2,
            offset=offset,
            fill=fill,
            position_policy="keep_cel_position",
        ),
    )
    assert (
        result["copied_source_rectangle"]
        == result["copied_target_rectangle"]
        == {"x": 0, "y": 0, "width": 0, "height": 0}
    )
    assert result["discarded_source_regions"] == [
        {"x": 0, "y": 0, "width": 2, "height": 2}
    ]
    assert result["uncovered_target_regions"] == [
        {"x": 0, "y": 0, "width": 3, "height": 2}
    ]
    for x, y in ((0, 0), (2, 1)):
        pixel = inspect_native(runtime, target, tmp_path, x, y)
        assert {key: pixel[key] for key in expected} == expected
        assert (pixel["width"], pixel["height"]) == (3, 2)


@pytest.mark.parametrize(
    "rectangle",
    [
        {"x": -1, "y": 0, "width": 1, "height": 1},
        {"x": 1, "y": 0, "width": 2, "height": 2},
        {"x": 0, "y": 2, "width": 1, "height": 1},
    ],
)
def test_crop_outside_source_cannot_pad_or_modify_source(
    tmp_path: Path, runtime: RuntimeObservation, rectangle: dict
) -> None:
    source = image_fixture(runtime, tmp_path)
    original = source.read_bytes()
    outcome = run(
        "image crop",
        transform_request(
            source,
            source,
            rectangle=rectangle,
            position_policy="keep_cel_position",
            in_place=True,
            overwrite=True,
        ),
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "image_crop_out_of_bounds"
    assert source.read_bytes() == original


@pytest.mark.parametrize("operation", ["crop", "canvas-resize"])
@pytest.mark.parametrize(
    ("mode", "layer", "frame", "failure"),
    [
        ("absent", 1, 2, "cel_not_found"),
        ("background", 1, 1, "cel_unsupported_target"),
        ("reference", 1, 1, "cel_unsupported_target"),
        ("tilemap", 2, 1, "cel_unsupported_target"),
        ("rgb", 1, 99, "cel_frame_out_of_bounds"),
    ],
)
def test_unsupported_targets_do_not_publish(
    tmp_path: Path,
    runtime: RuntimeObservation,
    operation: str,
    mode: str,
    layer: int,
    frame: int,
    failure: str,
) -> None:
    source = image_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    target = tmp_path / "rejected.aseprite"
    options = (
        {"rectangle": {"x": 0, "y": 0, "width": 1, "height": 1}}
        if operation == "crop"
        else {
            "width": 3,
            "height": 3,
            "offset": {"x": 0, "y": 0},
            "fill": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 0},
        }
    )
    outcome = run(
        f"image {operation}",
        transform_request(
            source,
            target,
            **options,
            target={"layer": {"layer_path": [layer]}, "frame_number": frame},
            position_policy="keep_cel_position",
        ),
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == failure
    assert not target.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("operation", "options"),
    [
        (
            "crop",
            {
                "rectangle": {"x": 1, "y": 0, "width": 1, "height": 2},
                "position_policy": "preserve_canvas_pixels",
            },
        ),
        (
            "canvas-resize",
            {
                "width": 2,
                "height": 2,
                "offset": {"x": -1, "y": 0},
                "fill": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 0},
                "position_policy": "preserve_source_canvas",
            },
        ),
    ],
)
def test_position_overflow_leaves_source_and_existing_target_unchanged(
    tmp_path: Path, runtime: RuntimeObservation, operation: str, options: dict
) -> None:
    source = image_fixture(runtime, tmp_path, "position-limit")
    original = source.read_bytes()
    output = tmp_path / "existing.aseprite"
    output.write_bytes(b"existing target must survive")
    outcome = run(
        f"image {operation}",
        transform_request(source, output, **options, overwrite=True),
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "image_transform_position_out_of_bounds"
    assert source.read_bytes() == original
    assert output.read_bytes() == b"existing target must survive"


@pytest.mark.parametrize(
    ("mode", "fill"),
    [
        ("rgb", {"kind": "palette-index", "index": 1}),
        ("grayscale", {"kind": "rgba", "red": 1, "green": 2, "blue": 3, "alpha": 255}),
        ("indexed", {"kind": "grayscale", "gray": 128, "alpha": 255}),
        ("indexed", {"kind": "palette-index", "index": 4}),
    ],
)
def test_incompatible_fill_is_rejected_before_publication(
    tmp_path: Path, runtime: RuntimeObservation, mode: str, fill: dict
) -> None:
    source = image_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    output = tmp_path / "rejected.aseprite"
    outcome = run(
        "image canvas-resize",
        transform_request(
            source,
            output,
            width=1,
            height=1,
            offset={"x": 100, "y": -100},
            fill=fill,
            position_policy="keep_cel_position",
        ),
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "image_canvas_fill_invalid"
    assert source.read_bytes() == original
    assert not output.exists()
