"""Native motion preflight refuses the whole range without Target publication."""

from pathlib import Path

import pytest

from tests.image.test_e2e_image_orientation import _fixture as unsupported_fixture
from tests.motion.test_e2e_motion import curves, fixture, run_motion

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("in_place", [False, True])
@pytest.mark.parametrize(
    ("case", "expected", "frame"),
    [
        ("missing", "cel_not_found", 5),
        ("linked", "motion_linked_cel", 1),
        ("overflow", "motion_position_out_of_bounds", 5),
        ("frame", "cel_frame_out_of_bounds", None),
    ],
)
def test_range_failure_preserves_target(
    tmp_path: Path, in_place: bool, case: str, expected: str, frame: int | None
) -> None:
    source = fixture(tmp_path, kind=case)
    frozen = source.read_bytes()
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(b"prior Target")
    prior = target.read_bytes()
    inputs = curves()
    if case == "linked":
        # Only Frame 1 is addressed; its linked peer is outside the range.
        inputs["to_frame"] = 1
        for name in ("position_offsets", "opacity"):
            inputs[name]["keys"] = inputs[name]["keys"][:1]
    elif case == "overflow":
        # Earlier targets are valid; the final target exceeds the coordinate bound.
        inputs["position_offsets"]["keys"][-1]["offset"]["x"] = 32767
    elif case == "frame":
        inputs["to_frame"] = 6
        for name in ("position_offsets", "opacity"):
            inputs[name]["keys"][-1]["frame_number"] = 6
    status, result = run_motion(source, target, inputs)
    assert status == 2, result
    assert result["code"] == expected
    if frame is not None:
        assert result["details"]["target"]["frame_number"] == frame
    assert source.read_bytes() == frozen
    assert target.read_bytes() == prior
    assert not list(tmp_path.glob(".*.staged.aseprite"))


@pytest.mark.parametrize(
    ("kind", "layer"),
    [("background", 1), ("reference", 1), ("tilemap", 2), ("group", 2)],
)
def test_motion_retains_cel_set_layer_eligibility(
    tmp_path: Path, kind: str, layer: int
) -> None:
    source = unsupported_fixture(tmp_path, kind=kind)
    target = tmp_path / "target.aseprite"
    inputs = {
        "layer": {"layer_path": [layer]},
        "from_frame": 1,
        "to_frame": 1,
        "opacity": {
            "interpolation": "step",
            "rounding": "floor",
            "keys": [{"frame_number": 1, "opacity": 0}],
        },
    }
    status, result = run_motion(source, target, inputs)
    assert status == 2, result
    assert result["code"] == "cel_unsupported_target"
    assert not target.exists()
