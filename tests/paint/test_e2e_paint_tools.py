"""Native Fill and freehand Paint through the public CLI."""

from pathlib import Path

import pytest

from tests.paint.support import call_spa

pytestmark = pytest.mark.e2e

RED = {"kind": "rgba", "red": 255, "green": 0, "blue": 0, "alpha": 255}


def create_sprite(destination: Path) -> None:
    code, result = call_spa(
        "sprite",
        "create",
        target_sprite_file=str(destination),
        width=8,
        height=6,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=False,
    )
    assert code == 0, result


def paint_request(source: Path, target: Path) -> dict:
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


def pixels(sprite: Path, *, frame: int = 1) -> list[list[dict]]:
    code, result = call_spa(
        "image",
        "get",
        sprite_file=str(sprite),
        source={
            "kind": "individual",
            "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
            "rectangle": {"x": 0, "y": 0, "width": 8, "height": 6},
        },
    )
    assert code == 0, result
    return [
        [segment["color"] for segment in row for _ in range(segment["length"])]
        for row in result["snapshot"]["rows"]
    ]


def test_pencil_keeps_one_ordered_gesture_and_persists_pixels(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    create_sprite(source)
    original = source.read_bytes()
    points = [{"x": 2, "y": 2}, {"x": 5, "y": 2}, {"x": 2, "y": 2}]
    code, result = call_spa(
        "paint",
        "pencil",
        **paint_request(source, target),
        points=points,
        freehand_algorithm="regular",
        brush={"kind": "circle", "size": 1},
        color=RED,
        ink="simple",
    )
    assert code == 0, result
    assert result["points"] == points
    assert result["freehand_algorithm"] == "regular"
    assert result["pixels_changed"] == result["pixels_requested"] == 4
    assert result["persisted_reopen_verified"]
    assert source.read_bytes() == original
    output = pixels(target)
    assert {
        (x, y)
        for y, row in enumerate(output)
        for x, color in enumerate(row)
        if color["alpha"]
    } == {(2, 2), (3, 2), (4, 2), (5, 2)}
