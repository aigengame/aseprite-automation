"""Bounded motion through the installed CLI and independent native pixel inspection."""

from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success
from tests.support import inspect_motion, motion_curves, motion_request, motion_sprite

pytestmark = pytest.mark.e2e


def test_motion_preserves_authored_poses_and_uses_each_cels_baseline(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = motion_sprite(runtime, tmp_path)
    before_bytes = source.read_bytes()
    before = inspect_motion(runtime, source, tmp_path)
    target = tmp_path / "motion.aseprite"
    result = expect_success(
        "motion apply", motion_request(source, target, motion_curves())
    )
    assert result["persisted_reopen_verified"] is True
    assert len(result["cels"]) == 5
    after = inspect_motion(runtime, target, tmp_path)
    moved = [cel for cel in after["cels"] if cel["layer"] == "wizard"]
    assert [(c["x"], c["y"]) for c in moved] == [
        (-2, 2),
        (0, 0),
        (1, -1),
        (3, -3),
        (4, -4),
    ]
    assert [c["opacity"] for c in moved] == [0, 63, 127, 191, 255]
    assert before["frames"] == after["frames"]
    for old, new in zip(before["cels"], after["cels"], strict=True):
        for field in ("pixels", "width", "height", "z", "links", "frame", "layer"):
            assert new[field] == old[field]
        if old["layer"] == "untouched":
            assert new == old
    assert source.read_bytes() == before_bytes


def test_full_native_displacement_and_position_boundaries_persist(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = motion_sprite(runtime, tmp_path, kind="boundary")
    inputs = motion_curves()
    inputs.update(to_frame=1, opacity=None)
    inputs["position_offsets"]["keys"] = [
        {"frame_number": 1, "offset": {"x": 65535, "y": -65535}}
    ]
    target = tmp_path / "boundary.aseprite"
    result = expect_success("motion apply", motion_request(source, target, inputs))
    assert result["cels"][0]["after"]["position"] == {"x": 32767, "y": -32768}
    reopened = inspect_motion(runtime, target, tmp_path)["cels"][0]
    assert (reopened["x"], reopened["y"]) == (32767, -32768)


def test_motion_target_count_is_not_limited_by_plan_step_count(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = motion_sprite(runtime, tmp_path, frame_count=65)
    inputs = motion_curves()
    inputs["to_frame"] = 65
    for name in ("position_offsets", "opacity"):
        inputs[name]["keys"][-1]["frame_number"] = 65
    result = expect_success(
        "motion apply", motion_request(source, tmp_path / "out.aseprite", inputs)
    )
    assert len(result["cels"]) == 65
    assert result["cels"][-1]["after"]["frame_number"] == 65
