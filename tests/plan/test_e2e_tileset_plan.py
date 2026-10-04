"""Atomic Tileset lifecycle composition through the public CLI."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support import spa
from tests.tile import conftest
from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e
runtime = conftest.runtime


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


def source_fixture(source: Path, runtime) -> None:
    fixture(source, runtime, script="../../plan/fixtures/tileset_lifecycle.lua")


def test_plan_rebinds_all_references_removes_and_keeps_step_time_cel_facts(
    tmp_path: Path,
    runtime,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source_fixture(source, runtime)
    original = source.read_bytes()
    code, result = run(
        "plan",
        "run",
        plan={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "steps": [
                {
                    "operation": "cel add",
                    "input": {
                        "target": {"layer": {"layer_name": "map"}, "frame_number": 2},
                        "tilemap_size": {"width": 2, "height": 1},
                    },
                },
                *lifecycle_steps(),
            ],
        },
    )
    assert code == 0, result
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
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target={"layer": {"layer_name": "map"}, "frame_number": 1},
    )
    assert code == 0, observed
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
    code, result = run(
        "plan",
        "run",
        plan={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "overwrite": True,
            "steps": [steps[0], steps[2]],
        },
    )
    assert code != 0, result
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
    code, result = run(
        "plan",
        "run",
        plan={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "overwrite": True,
            "steps": [
                *lifecycle_steps(),
                {
                    "operation": "cel add",
                    "input": {
                        "target": {"layer": {"layer_name": "map"}, "frame_number": 99},
                        "tilemap_size": {"width": 1, "height": 1},
                    },
                },
            ],
        },
    )
    assert code != 0, result
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
    observations_file = tmp_path / "observations.json"
    command = spa("--help").args[0]
    executed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "fixtures" / "observe_tileset_cli.py"),
            case,
            str(observations_file),
            command,
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
                }
            ),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    result = json.loads(executed.stdout)
    observations = json.loads(observations_file.read_text())
    assert observations["native_invocations"] == 1
    assert source.read_bytes() == original
    if failed_step is None:
        assert executed.returncode == 0, result
        assert observations["commits"] == 1
    else:
        assert executed.returncode != 0, result
        assert result["code"] == "kernel_response_invalid"
        assert result["details"]["failed_step"] == failed_step
        assert observations["commits"] == 0
        assert target.read_bytes() == b"Previous Target"
    assert not list(tmp_path.glob(".*.staged.aseprite"))
