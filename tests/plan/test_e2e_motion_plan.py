"""Motion shares native semantics and captures each Plan Step's current Cels."""

import json
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run
from tests.plan.support import observe_plan, plan_request, red_pixel
from tests.support import (
    inspect_motion,
    motion_curves,
    motion_request,
    motion_sprite,
    spa,
)

pytestmark = pytest.mark.e2e


def test_motion_plan_matches_standalone_and_defers_persistence(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = motion_sprite(runtime, tmp_path)
    standalone, planned = tmp_path / "standalone.aseprite", tmp_path / "plan.aseprite"
    inputs = motion_curves()
    expected = expect_success(
        "motion apply", motion_request(source, standalone, inputs)
    )
    result = expect_success(
        "plan run",
        plan_request(source, planned, [{"operation": "motion apply", "input": inputs}]),
    )
    assert result["persisted_reopen_verified"] is True
    validate(result, json.loads(spa("plan", "run", "--schema").stdout)["result_schema"])
    assert result["steps"][0]["result"] == {
        key: expected[key]
        for key in ("cels", "before_cel_count", "unchanged_facts_verified")
    } | {"persisted_reopen_verified": False}
    assert inspect_motion(runtime, planned, tmp_path) == inspect_motion(
        runtime, standalone, tmp_path
    )


def test_motion_uses_step_start_baselines_across_layers_and_later_edits(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = motion_sprite(runtime, tmp_path)
    frozen = source.read_bytes()
    inputs = motion_curves()
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
        {"operation": "paint apply", "input": red_pixel()},
        {
            "operation": "frame add",
            "input": {"frame_number": 2, "duration_ms": 150},
        },
    ]
    target = tmp_path / "combined.aseprite"
    result = expect_success("plan run", plan_request(source, target, steps))
    first = result["steps"][1]["result"]["cels"][2]
    second = result["steps"][2]["result"]["cels"][2]
    assert first["before"]["position"] == {"x": 100, "y": -100}
    assert (
        first["after"]["position"]
        == second["before"]["position"]
        == {"x": 101, "y": -101}
    )
    assert second["after"]["position"] == {"x": 102, "y": -102}
    final = inspect_motion(runtime, target, tmp_path)
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
    runtime: RuntimeObservation, tmp_path: Path, in_place: bool, kind: str, code: str
) -> None:
    source = motion_sprite(runtime, tmp_path, kind=kind)
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(b"existing Target")
    frozen, prior = source.read_bytes(), target.read_bytes()
    inputs = motion_curves()
    if kind == "linked":
        inputs["to_frame"] = 1
        for name in ("position_offsets", "opacity"):
            inputs[name]["keys"] = inputs[name]["keys"][:1]
    outcome = run(
        "plan run",
        plan_request(
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
        ),
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == code
    assert result["details"]["step_number"] == 2
    assert source.read_bytes() == frozen
    assert target.read_bytes() == prior
    assert not list(tmp_path.glob(".*.staged.aseprite"))


@pytest.mark.parametrize(
    "case", ["success", "motion_coverage", "motion_count", "unverified_save"]
)
def test_motion_plan_uses_one_process_and_gates_publication(
    runtime: RuntimeObservation, tmp_path: Path, case: str
) -> None:
    source = motion_sprite(runtime, tmp_path)
    target = tmp_path / "existing.aseprite"
    target.write_bytes(b"prior Target")
    process, result, _ = observe_plan(
        case,
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": True,
                "steps": [{"operation": "motion apply", "input": motion_curves()}],
            }
        },
        tmp_path,
    )
    if case == "success":
        assert process.returncode == 0, result
    else:
        assert process.returncode != 0, result
        assert result["code"] == "kernel_response_invalid"
        assert target.read_bytes() == b"prior Target"
