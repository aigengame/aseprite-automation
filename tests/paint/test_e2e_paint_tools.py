"""Native Fill and freehand Paint through the public CLI."""

from pathlib import Path

import pytest

from tests.native_invocation import expect_success
from tests.paint.support import RED, create_sprite, read_pixels

pytestmark = pytest.mark.e2e


def paint_request(source: Path, target: Path) -> dict:
    """Return the Paint request fields that address Layer 1, Frame 1 of source.

    The request writes a new target at full opacity and rejects clipping.
    """
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        "opacity": 255,
        "clipping": "reject",
    }


def test_pencil_keeps_one_ordered_gesture_and_persists_pixels(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    create_sprite(source)
    original = source.read_bytes()
    points = [{"x": 2, "y": 2}, {"x": 5, "y": 2}, {"x": 2, "y": 2}]
    result = expect_success(
        "paint pencil",
        {
            **paint_request(source, target),
            "points": points,
            "freehand_algorithm": "regular",
            "brush": {"kind": "circle", "size": 1},
            "color": RED,
            "ink": "simple",
        },
    )
    assert result["points"] == points
    assert result["freehand_algorithm"] == "regular"
    assert result["pixels_changed"] == result["pixels_requested"] == 4
    assert result["persisted_reopen_verified"]
    assert source.read_bytes() == original
    output = read_pixels(target)
    assert {
        (x, y)
        for y, row in enumerate(output)
        for x, color in enumerate(row)
        if color["alpha"]
    } == {(2, 2), (3, 2), (4, 2), (5, 2)}


def test_fill_uses_original_canvas_and_reports_native_matching(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "filled.aseprite"
    create_sprite(source)
    result = expect_success(
        "paint fill",
        {
            **paint_request(source, target),
            "seed": {"x": 0, "y": 0},
            "color": RED,
            "ink": "simple",
            "tolerance": 0,
            "contiguous": True,
            "connectivity": "four-connected",
            "refer_to": "active-layer",
            "stop_at_grid": False,
        },
    )
    assert result["pixels_requested"] == result["pixels_changed"] == 48
    assert result["source_scope"] == {
        "kind": "active-layer",
        "frame_number": 1,
        "canvas_bounds": {"x": 0, "y": 0, "width": 8, "height": 6},
    }
    assert result["effective_grid_cell"] is None
    assert all(color == RED for row in read_pixels(target) for color in row)
