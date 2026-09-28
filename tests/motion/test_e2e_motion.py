"""Bounded motion through the installed CLI and independent native pixel inspection."""

import json
import os
from pathlib import Path

import pytest

from tests.frame.test_e2e_frame import _run_fixture
from tests.support import spa

pytestmark = pytest.mark.e2e


def native(name: str, **parameters: object) -> None:
    _run_fixture(
        str(Path(__file__).parent / "fixtures" / name),
        **{key: str(value) for key, value in parameters.items()},
    )


def fixture(tmp_path: Path, **parameters: object) -> Path:
    source = tmp_path / "source.aseprite"
    native("poses.lua", out=source, **parameters)
    assert source.is_file()
    return source


def inspect(source: Path, tmp_path: Path) -> dict:
    out = tmp_path / "inspection.json"
    native("inspect.lua", source=source, out=out)
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
    tmp_path: Path,
) -> None:
    source = fixture(tmp_path)
    before_bytes = source.read_bytes()
    before = inspect(source, tmp_path)
    target = tmp_path / "motion.aseprite"
    code, result = run_motion(source, target, curves())
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    assert len(result["cels"]) == 5
    after = inspect(target, tmp_path)
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
