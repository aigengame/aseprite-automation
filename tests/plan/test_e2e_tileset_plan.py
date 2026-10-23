"""Atomic Tileset lifecycle composition through the public CLI."""

import hashlib
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run, run_lua
from tests.plan.support import FIXTURES, observe_plan
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


def lifecycle_steps() -> list[dict]:
    return [
        {
            "operation": "layer set-tileset",
            "input": {
                "layer": {"layer_name": name},
                "target": {"tileset_index": 2},
                "mapping": {"kind": "by_key"},
                "grid_policy": "require_equal",
            },
        }
        for name in ("map", "peer")
    ] + [
        {
            "operation": "tileset remove",
            "input": {
                "target": {"tileset_index": 1},
            },
        }
    ]


def source_fixture(source: Path, runtime: RuntimeObservation) -> None:
    """Write the Tileset lifecycle Plan Sprite of `tileset_lifecycle.lua` to source."""
    lua = run_lua(
        FIXTURES / "tileset_lifecycle.lua",
        runtime,
        source=source,
    )
    assert lua.returncode == 0, process_diagnostics(lua)


def test_plan_rebinds_all_references_removes_and_keeps_step_time_cel_facts(
    tmp_path: Path,
    runtime,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source_fixture(source, runtime)
    original = source.read_bytes()
    result = expect_success(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "steps": [
                    {
                        "operation": "cel add",
                        "input": {
                            "target": {
                                "layer": {"layer_name": "map"},
                                "frame_number": 2,
                            },
                            "tilemap_size": {"width": 2, "height": 1},
                        },
                    },
                    *lifecycle_steps(),
                ],
            }
        },
    )
    assert source.read_bytes() == original
    assert result["persisted_reopen_verified"] is True
    assert (
        result["target_commit"]["sha256"]
        == hashlib.sha256(target.read_bytes()).hexdigest()
    )
    add, rebind, peer, removal = [step["result"] for step in result["steps"]]
    assert add["tilemap_creation"]["tileset"]["name"] == "terrain"
    assert rebind["tileset"]["tileset_index"] == peer["tileset"]["tileset_index"] == 2
    assert removal["removed_tileset"]["tileset_index"] == 1
    assert removal["tilesets"][0]["tileset_index"] == 1
    assert result["final_sprite"]["tilesets"][0]["name"] == "replacement"
    observed = expect_success(
        "tilemap get",
        {
            "sprite_file": str(target),
            "target": {"layer": {"layer_name": "map"}, "frame_number": 1},
        },
    )
    assert observed["tilemap"]["position"] == {"x": -2, "y": 4}


def test_plan_later_referenced_removal_reports_remaining_reference_and_rolls_back(
    tmp_path: Path,
    runtime,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source_fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"Existing Target must survive the failed Plan")
    steps = lifecycle_steps()
    outcome = run(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": True,
                "steps": [steps[0], steps[2]],
            }
        },
    )
    result = outcome.envelope
    assert outcome.returncode != 0, result
    assert result["code"] == "tileset_in_use"
    assert result["details"]["step_number"] == 2
    assert result["details"]["tileset"]["name"] == "terrain"
    assert [layer["name"] for layer in result["details"]["layers"]] == ["peer"]
    assert source.read_bytes() == original
    assert target.read_bytes() == b"Existing Target must survive the failed Plan"
    assert not list(tmp_path.glob(".*.staged.aseprite"))


def test_plan_failure_after_rebind_and_removal_preserves_source_and_target(
    tmp_path: Path,
    runtime,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source_fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"Previous Target")
    outcome = run(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": True,
                "steps": [
                    *lifecycle_steps(),
                    {
                        "operation": "cel add",
                        "input": {
                            "target": {
                                "layer": {"layer_name": "map"},
                                "frame_number": 99,
                            },
                            "tilemap_size": {"width": 1, "height": 1},
                        },
                    },
                ],
            }
        },
    )
    result = outcome.envelope
    assert outcome.returncode != 0, result
    assert result["code"] == "cel_frame_out_of_bounds"
    assert result["details"]["step_number"] == 4
    assert result["details"]["from_frame"] == result["details"]["to_frame"] == 99
    assert source.read_bytes() == original
    assert target.read_bytes() == b"Previous Target"
    assert not list(tmp_path.glob(".*.staged.aseprite"))


@pytest.mark.parametrize(
    "case,failed_step", [("none", None), ("cel_grid", 1), ("collection_order", 4)]
)
def test_plan_verifies_step_time_tileset_evidence_before_its_only_commit(
    tmp_path: Path,
    runtime,
    case: str,
    failed_step: int | None,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source_fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"Previous Target")
    executed, result, _ = observe_plan(
        case,
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": True,
                "steps": [
                    {
                        "operation": "cel add",
                        "input": {
                            "target": {
                                "layer": {"layer_name": "map"},
                                "frame_number": 2,
                            },
                            "tilemap_size": {"width": 2, "height": 1},
                        },
                    },
                    *lifecycle_steps(),
                ],
            },
        },
        tmp_path,
    )
    assert source.read_bytes() == original
    if failed_step is None:
        assert executed.returncode == 0, result
    else:
        assert executed.returncode != 0, result
        assert result["code"] == "kernel_response_invalid"
        assert result["details"]["failed_step"] == failed_step
        assert target.read_bytes() == b"Previous Target"
