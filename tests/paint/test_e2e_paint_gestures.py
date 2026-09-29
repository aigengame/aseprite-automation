"""Contour and Blur retain one native gesture and persist its exact pixels."""

from pathlib import Path

import pytest

from tests.paint.test_e2e_native_paint import RED, _call, _native_fixture, _pixels
from tests.support import inject_palette_change

pytestmark = pytest.mark.e2e

POINTS = [{"x": 2, "y": 1}, {"x": 5, "y": 1}, {"x": 5, "y": 4}, {"x": 2, "y": 4}]


def _gesture(
    source: Path, destination: Path, operation: str = "contour", **options: object
):
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(destination),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        "points": POINTS,
        "brush": {"kind": "circle", "size": 1},
        "opacity": 255,
        "freehand_algorithm": "regular",
        "clipping": "reject",
    }
    if operation == "contour":
        request |= {"color": RED, "ink": "simple"}
    return _call("paint", operation, **(request | options))


@pytest.mark.parametrize("algorithm", ["regular", "pixel-perfect"])
@pytest.mark.parametrize(
    "ink", ["simple", "alpha-compositing", "copy-color", "lock-alpha"]
)
@pytest.mark.parametrize("opacity", [0, 128, 255])
def test_contour_persists_one_native_gesture(
    tmp_path: Path, algorithm: str, ink: str, opacity: int
) -> None:
    source, expected = _native_fixture(
        tmp_path,
        reference=True,
        tool="contour",
        points=POINTS,
        brush={"kind": "circle", "size": 1},
        ink=ink,
        opacity=opacity,
        freehand_algorithm=algorithm,
    )
    original = source.read_bytes()
    target = tmp_path / "contour.aseprite"
    run, result = _gesture(
        source, target, ink=ink, opacity=opacity, freehand_algorithm=algorithm
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert _pixels(target) == _pixels(expected)
    assert source.read_bytes() == original
    assert result["points"] == POINTS
    assert result["freehand_algorithm"] == algorithm
    assert result["requested_opacity"] == opacity
    effective = 255 if ink in {"simple", "copy-color"} else opacity
    assert result["effective_opacity"] == effective
    assert (result["pixels_changed"] > 0) == (effective > 0)
    assert result["persisted_reopen_verified"] is True


@pytest.mark.parametrize("tiled", ["none", "x", "y", "both"])
@pytest.mark.parametrize("opacity", [0, 128, 255])
@pytest.mark.parametrize("algorithm", ["regular", "pixel-perfect"])
def test_blur_uses_the_native_document_edge_for_tiled_sampling(
    tmp_path: Path, tiled: str, opacity: int, algorithm: str
) -> None:
    points = [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]
    brush = {"kind": "circle", "size": 3}
    source, expected = _native_fixture(
        tmp_path,
        reference=True,
        tool="blur",
        points=points,
        brush=brush,
        opacity=opacity,
        freehand_algorithm=algorithm,
        tiled_mode=tiled,
        pattern=True,
    )
    target = tmp_path / "blurred.aseprite"
    run, result = _gesture(
        source,
        target,
        "blur",
        points=points,
        brush=brush,
        opacity=opacity,
        tiled_mode=tiled,
        freehand_algorithm=algorithm,
        clipping="clip",
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert _pixels(target) == _pixels(expected)
    assert result["ink"] == "blur" and "color" not in result
    assert result["tiled_mode"] == tiled
    assert result["points"] == points
    assert result["requested_opacity"] == result["effective_opacity"] == opacity
    assert result["persisted_reopen_verified"] is True
    assert (result["pixels_changed"] > 0) == (opacity > 0)
    assert result["pixels_written"] > 0


@pytest.mark.parametrize("algorithm", ["regular", "pixel-perfect"])
@pytest.mark.parametrize("mode", ["grayscale", "indexed"])
@pytest.mark.parametrize("tiled", ["none", "x", "y", "both"])
def test_blur_color_modes_and_oriented_brushes_match_native(
    tmp_path: Path, algorithm: str, mode: str, tiled: str
) -> None:
    brush = {"kind": "line", "size": 5, "angle": -45}
    points = [{"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 0, "y": 1}]
    source, expected = _native_fixture(
        tmp_path,
        reference=True,
        tool="blur",
        points=points,
        brush=brush,
        mode=mode,
        opacity=128,
        freehand_algorithm=algorithm,
        tiled_mode=tiled,
        pattern=True,
    )
    target = tmp_path / "blurred.aseprite"
    run, result = _gesture(
        source,
        target,
        "blur",
        points=points,
        brush=brush,
        opacity=128,
        freehand_algorithm=algorithm,
        tiled_mode=tiled,
        clipping="clip",
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert _pixels(target) == _pixels(expected)
    assert result["color_mode"] == mode
    assert bool(result["effective_palettes"]) == (mode == "indexed")


@pytest.mark.parametrize("tiled", ["none", "x", "y", "both"])
def test_blur_offset_linked_cel_preserves_original_geometry_and_native_coverage(
    tmp_path: Path, tiled: str
) -> None:
    points = [{"x": 2, "y": 0}]
    brush = {"kind": "square", "size": 3, "angle": 0}
    source, expected = _native_fixture(
        tmp_path,
        reference=True,
        tool="blur",
        points=points,
        brush=brush,
        opacity=255,
        freehand_algorithm="regular",
        tiled_mode=tiled,
        pattern=True,
        offset=True,
        linked=True,
        preserve_geometry=True,
    )
    original = _pixels(source)
    target = tmp_path / "blurred.aseprite"
    run, result = _gesture(
        source,
        target,
        "blur",
        points=points,
        brush=brush,
        tiled_mode=tiled,
        clipping="clip",
    )
    assert run.returncode == 0, run.stdout + run.stderr
    actual = _pixels(target)
    assert actual == _pixels(expected)
    assert actual == _pixels(target, frame=2)
    assert _pixels(target, frame=3) == original
    assert result["linked_cels_preserved"] and result["geometry_unchanged"]
    assert all(cel["position"] == {"x": -2, "y": 3} for cel in result["affected_cels"])


@pytest.mark.parametrize(
    "points",
    [
        [{"x": 2, "y": 2}],
        [{"x": 2, "y": 2}] * 3,
        [
            {"x": 1, "y": 1},
            {"x": 2, "y": 1},
            {"x": 2, "y": 2},
            {"x": 3, "y": 2},
            {"x": 3, "y": 3},
            {"x": 4, "y": 3},
        ],
        [
            {"x": 1, "y": 1},
            {"x": 5, "y": 4},
            {"x": 1, "y": 4},
            {"x": 5, "y": 1},
            {"x": 5, "y": 1},
            {"x": 1, "y": 1},
        ],
    ],
)
@pytest.mark.parametrize("algorithm", ["regular", "pixel-perfect"])
def test_contour_degenerate_repeated_and_crossing_gestures_match_native(
    tmp_path: Path, points: list[dict], algorithm: str
) -> None:
    source, expected = _native_fixture(
        tmp_path,
        reference=True,
        tool="contour",
        points=points,
        brush={"kind": "circle", "size": 1},
        ink="simple",
        opacity=255,
        freehand_algorithm=algorithm,
    )
    target = tmp_path / "contour.aseprite"
    run, result = _gesture(source, target, points=points, freehand_algorithm=algorithm)
    assert run.returncode == 0, run.stdout + run.stderr
    assert result["points"] == points
    assert _pixels(target) == _pixels(expected)


@pytest.mark.parametrize("operation", ["contour", "blur"])
def test_gesture_selection_filters_writes_without_changing_native_pixels(
    tmp_path: Path, operation: str
) -> None:
    brush = {"kind": "square", "size": 3, "angle": 45}
    source, expected = _native_fixture(
        tmp_path,
        reference=True,
        tool=operation,
        points=POINTS,
        brush=brush,
        ink="simple",
        opacity=255,
        pattern=True,
        tiled_mode="none",
    )
    original, reference = _pixels(source), _pixels(expected)
    target = tmp_path / "selected.aseprite"
    options = {"tiled_mode": "none"} if operation == "blur" else {}
    run, result = _gesture(
        source,
        target,
        operation,
        brush=brush,
        clipping="clip",
        selection={
            "kind": "all",
            "rectangle": {"x": 3, "y": 2, "width": 2, "height": 2},
        },
        **options,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    pixels = _pixels(target)
    for y in range(6):
        for x in range(8):
            assert pixels[y][x] == (
                reference[y][x] if 3 <= x < 5 and 2 <= y < 4 else original[y][x]
            )
    assert result["pixels_skipped_by_selection"] > 0


@pytest.mark.parametrize("operation", ["contour", "blur"])
def test_gesture_uses_the_addressed_frames_effective_palette(
    tmp_path: Path, operation: str
) -> None:
    source, _ = _native_fixture(tmp_path, mode="indexed", pattern=True, linked=True)
    inject_palette_change(
        source,
        [
            (0, 0, 0, 255),
            (255, 255, 255, 255),
            (255, 0, 255, 255),
            (128, 128, 128, 255),
            (0, 255, 255, 255),
            (255, 255, 0, 255),
            (0, 255, 0, 255),
            (0, 0, 0, 0),
        ],
    )
    reference_dir = tmp_path / "oracle"
    reference_dir.mkdir()
    brush = {"kind": "circle", "size": 1}
    _, expected = _native_fixture(
        reference_dir,
        reference=True,
        source_sprite_file=str(source),
        mode="indexed",
        frame_number=2,
        tool=operation,
        points=POINTS,
        brush=brush,
        opacity=128,
        ink="alpha-compositing",
        tiled_mode="none",
        freehand_algorithm="regular",
    )
    options = (
        {"tiled_mode": "none"}
        if operation == "blur"
        else {
            "color": {"kind": "palette-index", "index": 2},
            "ink": "alpha-compositing",
        }
    )
    target = tmp_path / "frame-2.aseprite"
    run, result = _gesture(
        source,
        target,
        operation,
        opacity=128,
        target={"layer": {"layer_path": [1]}, "frame_number": 2},
        **options,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert _pixels(target, frame=2) == _pixels(expected, frame=2)
    assert _pixels(target) == _pixels(target, frame=2)
    assert {
        (item["frame_number"], item["palette_frame_number"])
        for item in result["effective_palettes"]
    } == {(1, 1), (2, 2)}


@pytest.mark.parametrize("operation", ["contour", "blur"])
def test_gesture_preserves_background_opacity(tmp_path: Path, operation: str) -> None:
    source, expected = _native_fixture(
        tmp_path,
        reference=True,
        tool=operation,
        points=POINTS,
        brush={"kind": "circle", "size": 1},
        ink="simple",
        opacity=128,
        pattern=True,
        background=True,
        tiled_mode="both",
    )
    target = tmp_path / "background.aseprite"
    options = {"tiled_mode": "both"} if operation == "blur" else {}
    run, result = _gesture(source, target, operation, opacity=128, **options)
    assert run.returncode == 0, run.stdout + run.stderr
    assert _pixels(target) == _pixels(expected)
    assert result["background_opaque"] is True


def test_gradient_gap_is_reported_without_corrupting_runtime_discovery() -> None:
    run, result = _call("schema")
    assert run.returncode == 0, run.stdout + run.stderr
    available = {entry["operation"] for entry in result["operations"]}
    assert {"spa paint contour", "spa paint blur"} <= available
    assert "spa paint gradient" not in available
    gap = next(
        gap
        for gap in result["capability_gaps"]
        if gap["capability"] == "spa paint gradient"
    )
    assert gap["aseprite_version"] == result["runtime"]["aseprite_version"]
    assert "Gradient Type" in gap["evidence"] and "Dithering Matrix" in gap["evidence"]
