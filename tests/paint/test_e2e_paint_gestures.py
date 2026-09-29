"""Contour and Blur retain one native gesture and persist its exact pixels."""

from pathlib import Path

import pytest

from tests.paint.test_e2e_native_paint import RED, _call, _native_fixture, _pixels

pytestmark = pytest.mark.e2e

POINTS = [{"x": 2, "y": 1}, {"x": 5, "y": 1}, {"x": 5, "y": 4}, {"x": 2, "y": 4}]


def _gesture(source: Path, target: Path, operation: str = "contour", **options: object):
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
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
