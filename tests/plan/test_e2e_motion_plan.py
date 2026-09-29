"""Motion shares native semantics and captures each Plan Step's current Cels."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import validate

from tests.motion.test_e2e_motion import curves, fixture, inspect, run_motion
from tests.plan.test_e2e_plan import _red_pixel
from tests.support import spa

pytestmark = pytest.mark.e2e


def plan(source: Path, target: Path, steps: list[dict]) -> tuple[int, dict]:
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "plan": {
                    "source_sprite_file": str(source),
                    "target_sprite_file": str(target),
                    "in_place": source == target,
                    "overwrite": target.exists(),
                    "steps": steps,
                },
            }
        ),
    )
    assert run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)


def test_motion_plan_matches_standalone_and_defers_persistence(tmp_path: Path) -> None:
    source = fixture(tmp_path)
    standalone, planned = tmp_path / "standalone.aseprite", tmp_path / "plan.aseprite"
    inputs = curves()
    code, expected = run_motion(source, standalone, inputs)
    assert code == 0, expected
    code, result = plan(
        source, planned, [{"operation": "motion apply", "input": inputs}]
    )
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    validate(result, json.loads(spa("plan", "run", "--schema").stdout)["result_schema"])
    assert result["steps"][0]["result"] == {
        key: expected[key]
        for key in ("cels", "before_cel_count", "unchanged_facts_verified")
    } | {"persisted_reopen_verified": False}
    assert inspect(planned, tmp_path) == inspect(standalone, tmp_path)


def test_motion_uses_step_start_baselines_across_layers_and_later_edits(
    tmp_path: Path,
) -> None:
    source = fixture(tmp_path)
    frozen = source.read_bytes()
    inputs = curves()
    other = {
        "layer": {"layer_name": "untouched"},
        "from_frame": 1,
        "to_frame": 1,
        "opacity": {
            "interpolation": "step",
            "rounding": "floor",
            "keys": [{"frame_number": 1, "opacity": 70}],
        },
    }
    steps = [
        {
            "operation": "cel set",
            "input": {
                "target": {"layer": {"layer_path": [1]}, "frame_number": 3},
                "position": {"x": 100, "y": -100},
            },
        },
        {"operation": "motion apply", "input": inputs},
        {"operation": "motion apply", "input": inputs},
        {"operation": "motion apply", "input": other},
        {"operation": "paint apply", "input": _red_pixel()},
        {
            "operation": "frame add",
            "input": {"frame_number": 2, "duration_ms": 150},
        },
    ]
    target = tmp_path / "combined.aseprite"
    code, result = plan(source, target, steps)
    assert code == 0, result
    first = result["steps"][1]["result"]["cels"][2]
    second = result["steps"][2]["result"]["cels"][2]
    assert first["before"]["position"] == {"x": 100, "y": -100}
    assert (
        first["after"]["position"]
        == second["before"]["position"]
        == {"x": 101, "y": -101}
    )
    assert second["after"]["position"] == {"x": 102, "y": -102}
    final = inspect(target, tmp_path)
    assert len(final["frames"]) == 6
    assert (
        next(c for c in final["cels"] if c["layer"] == "wizard" and c["frame"] == 4)[
            "x"
        ]
        == 102
    )
    assert next(c for c in final["cels"] if c["layer"] == "untouched")["opacity"] == 70
    assert final["cels"][0]["pixels"][0] == 4278190335  # Stored opaque red.
    assert source.read_bytes() == frozen


@pytest.mark.parametrize("in_place", [False, True])
@pytest.mark.parametrize(
    ("kind", "code"), [("missing", "cel_not_found"), ("linked", "motion_linked_cel")]
)
def test_motion_failure_after_prior_plan_work_does_not_publish(
    tmp_path: Path, in_place: bool, kind: str, code: str
) -> None:
    source = fixture(tmp_path, kind=kind)
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(b"existing Target")
    frozen, prior = source.read_bytes(), target.read_bytes()
    inputs = curves()
    if kind == "linked":
        inputs["to_frame"] = 1
        for name in ("position_offsets", "opacity"):
            inputs[name]["keys"] = inputs[name]["keys"][:1]
    status, result = plan(
        source,
        target,
        [
            {
                "operation": "cel set",
                "input": {
                    "target": {"layer": {"layer_path": [2]}, "frame_number": 1},
                    "opacity": 0,
                },
            },
            {"operation": "motion apply", "input": inputs},
        ],
    )
    assert status == 2, result
    assert result["code"] == code
    assert result["details"]["step_number"] == 2
    assert source.read_bytes() == frozen
    assert target.read_bytes() == prior
    assert not list(tmp_path.glob(".*.staged.aseprite"))


@pytest.mark.parametrize(
    "case", ["success", "motion_coverage", "motion_count", "unverified_save"]
)
def test_motion_plan_uses_one_process_and_gates_publication(
    tmp_path: Path, case: str
) -> None:
    source = fixture(tmp_path)
    target = tmp_path / "existing.aseprite"
    target.write_bytes(b"prior Target")
    observations_path = tmp_path / "observations.json"
    cli = shutil.which("spa")
    assert cli
    run = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "fixtures" / "observe_cli.py"),
            case,
            str(observations_path),
            cli,
            "plan",
            "run",
            "--input-json",
            json.dumps(
                {
                    "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                    "plan": {
                        "source_sprite_file": str(source),
                        "target_sprite_file": str(target),
                        "overwrite": True,
                        "steps": [{"operation": "motion apply", "input": curves()}],
                    },
                }
            ),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.stdout, run.stderr
    result = json.loads(run.stdout)
    observations = json.loads(observations_path.read_text())
    assert observations["native_invocations"] == 1
    if case == "success":
        assert run.returncode == 0, result
        assert observations["commits"] == 1
    else:
        assert run.returncode != 0, result
        assert observations["commits"] == 0
        assert result["code"] == "kernel_response_invalid"
        assert target.read_bytes() == b"prior Target"
    assert not list(tmp_path.glob(".*.staged.aseprite"))
