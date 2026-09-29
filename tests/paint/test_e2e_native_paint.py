"""Native Paint through the public CLI, with saved Image facts as evidence."""

import json
import os
from pathlib import Path

import pytest

from tests.support import spa

pytestmark = pytest.mark.e2e

RED = {"kind": "rgba", "red": 255, "green": 0, "blue": 0, "alpha": 255}


def _call(*command: str, **request: object):
    run = spa(
        *command,
        "--input-json",
        "-",
        stdin=json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"], **request}),
    )
    return run, json.loads(run.stdout) if run.stdout else {}


def _create(source: Path) -> None:
    run, result = _call(
        "sprite",
        "create",
        target_sprite_file=str(source),
        width=8,
        height=6,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=False,
    )
    assert run.returncode == 0, result


def _paint(source: Path, target: Path, primitive: str = "line", **options: object):
    geometry = {"from": {"x": 2, "y": 2}, "to": {"x": 5, "y": 2}}
    if primitive != "line":
        geometry = {
            "bounds": {"x": 2, "y": 2, "width": 4, "height": 3},
            "style": "outline",
        }
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        "brush": {"kind": "circle", "size": 1},
        "color": RED,
        "ink": "simple",
        "opacity": 255,
        "clipping": "reject",
    }
    return _call("paint", primitive, **(request | geometry | options))


def _pixels(source: Path) -> list[list[dict]]:
    run, result = _call(
        "image",
        "get",
        sprite_file=str(source),
        source={
            "kind": "individual",
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "rectangle": {"x": 0, "y": 0, "width": 8, "height": 6},
        },
    )
    assert run.returncode == 0, result
    return [
        [segment["color"] for segment in row for _ in range(segment["length"])]
        for row in result["snapshot"]["rows"]
    ]


def test_line_persists_native_pixels_without_resizing_the_cel(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _create(source)
    original = source.read_bytes()
    run, result = _paint(source, target)
    assert run.returncode == 0, run.stdout + run.stderr
    assert (
        result["pixels_requested"]
        == result["pixels_written"]
        == result["pixels_changed"]
        == 4
    )
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original
    pixels = _pixels(target)
    assert {
        (x, y)
        for y, row in enumerate(pixels)
        for x, color in enumerate(row)
        if color["alpha"]
    } == {
        (2, 2),
        (3, 2),
        (4, 2),
        (5, 2),
    }
    assert all(pixels[2][x] == RED for x in range(2, 6))


def test_filled_rectangle_uses_half_open_bounds(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "rectangle.aseprite"
    _create(source)
    run, result = _paint(source, target, "rectangle", style="filled")
    assert run.returncode == 0, run.stdout + run.stderr
    assert result["pixels_changed"] == 12
    pixels = _pixels(target)
    assert {
        (x, y)
        for y, row in enumerate(pixels)
        for x, color in enumerate(row)
        if color["alpha"]
    } == {(x, y) for y in (2, 3, 4) for x in (2, 3, 4, 5)}
