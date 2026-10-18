"""Bounded motion through the installed CLI and independent native pixel inspection."""

import json
import os
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(runtime: RuntimeObservation, tmp_path: Path, **parameters: object) -> Path:
    """Write the posed motion Sprite to tmp_path, and return its path."""
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "poses.lua", runtime, out=source, **parameters)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    return source


def inspect(runtime: RuntimeObservation, source: Path, tmp_path: Path) -> dict:
    """Read the native Frames and Cels of source with the inspection fixture."""
    out = tmp_path / "inspection.json"
    lua = run_lua(FIXTURES / "inspect.lua", runtime, source=source, out=out)
    assert lua.returncode == 0, process_diagnostics(lua)
    return json.loads(out.read_text())


def curves() -> dict:
    return {
        "layer": {"layer_path": [1]},
        "from_frame": 1,
        "to_frame": 5,
        "position_offsets": {
            "interpolation": "linear",
            "rounding": "nearest-away-from-zero",
            "keys": [
                {"frame_number": 1, "offset": {"x": 0, "y": 0}},
                {"frame_number": 5, "offset": {"x": 2, "y": -2}},
            ],
        },
        "opacity": {
            "interpolation": "linear",
            "rounding": "floor",
            "keys": [
                {"frame_number": 1, "opacity": 0},
                {"frame_number": 5, "opacity": 255},
            ],
        },
    }


def run_motion(source: Path, target: Path, inputs: dict) -> tuple[int, dict]:
    run = spa(
        "motion",
        "apply",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": source == target,
                "overwrite": target.exists(),
                **inputs,
            }
        ),
    )
    assert run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)


def test_motion_preserves_authored_poses_and_uses_each_cels_baseline(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = fixture(runtime, tmp_path)
    before_bytes = source.read_bytes()
    before = inspect(runtime, source, tmp_path)
    target = tmp_path / "motion.aseprite"
    code, result = run_motion(source, target, curves())
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    assert len(result["cels"]) == 5
    after = inspect(runtime, target, tmp_path)
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
    source = fixture(runtime, tmp_path, kind="boundary")
    inputs = curves()
    inputs.update(to_frame=1, opacity=None)
    inputs["position_offsets"]["keys"] = [
        {"frame_number": 1, "offset": {"x": 65535, "y": -65535}}
    ]
    target = tmp_path / "boundary.aseprite"
    code, result = run_motion(source, target, inputs)
    assert code == 0, result
    assert result["cels"][0]["after"]["position"] == {"x": 32767, "y": -32768}
    reopened = inspect(runtime, target, tmp_path)["cels"][0]
    assert (reopened["x"], reopened["y"]) == (32767, -32768)


def test_motion_target_count_is_not_limited_by_plan_step_count(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = fixture(runtime, tmp_path, frame_count=65)
    inputs = curves()
    inputs["to_frame"] = 65
    for name in ("position_offsets", "opacity"):
        inputs[name]["keys"][-1]["frame_number"] = 65
    code, result = run_motion(source, tmp_path / "out.aseprite", inputs)
    assert code == 0, result
    assert len(result["cels"]) == 65
    assert result["cels"][-1]["after"]["frame_number"] == 65
