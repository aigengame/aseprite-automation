"""Ownership and native facts at the shared Sprite persistence boundary."""

import json
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import pytest

from tests.frame.test_e2e_frame import _run_fixture
from tests.motion.test_e2e_motion import curves, fixture

pytestmark = pytest.mark.e2e


def run_verified_save(tmp_path: Path, case: str) -> None:
    kernel = files("spa.kernel")
    _run_fixture(
        str(Path(__file__).parent / "fixtures" / "verified_save.lua"),
        persistence=str(kernel.joinpath("sprite_persistence.lua")),
        inspection=str(kernel.joinpath("sprite_inspect.lua")),
        digest=str(kernel.joinpath("digest.lua")),
        staged=str(tmp_path / "staged.aseprite"),
        case=case,
    )


def test_verified_save_transfers_ownership_and_returns_fresh_facts(
    tmp_path: Path,
) -> None:
    run_verified_save(tmp_path, "success")
    assert (tmp_path / "staged.aseprite").is_file()


@pytest.mark.parametrize("case", ["save", "reopen", "observation", "comparison"])
def test_verified_save_closes_owned_sprites_on_failure(
    tmp_path: Path,
    case: str,
) -> None:
    run_verified_save(tmp_path, case)


@pytest.mark.parametrize("operation", ["cel set", "motion apply"])
@pytest.mark.parametrize(
    "case", ["success", "save", "reopen", "observation", "comparison"]
)
@pytest.mark.parametrize("in_place", [False, True])
def test_handlers_gate_commit_and_restore_editor_on_persistence_failure(
    tmp_path: Path,
    operation: str,
    case: str,
    in_place: bool,
) -> None:
    source = fixture(tmp_path, uuids="true")
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(b"prior Target")
    before_source, before_target = source.read_bytes(), target.read_bytes()
    inputs = (
        curves()
        if operation == "motion apply"
        else {
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "opacity": 42,
        }
    )
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": in_place,
        "overwrite": True,
        **inputs,
    }
    outcome, observations = observed_cli(tmp_path, operation, request, case)
    assert observations["handler_invocations"] == observations["saves"] == 1
    assert observations["probe_invocations"] == 1
    assert observations["editor_restored"] is True
    assert observations["owned_sprites_closed"] is True
    if case == "success":
        assert outcome["status"] == "success", outcome
        assert outcome["persisted_reopen_verified"] is True
        assert observations["commits"] == 1
        assert observations["staged_opens"] == 2
    else:
        assert outcome["code"] == "kernel_execution_failed", outcome
        reasons = {
            "save": "could not save staged Sprite",
            "reopen": "could not reopen staged Sprite",
            "observation": "could not reopen Sprite for UUID verification",
            "comparison": "differs at document",
        }
        assert reasons[case] in outcome["details"]["reason"]
        assert (
            observations["staged_opens"]
            == {
                "save": 0,
                "reopen": 1,
                "observation": 2,
                "comparison": 2,
            }[case]
        )
        assert observations["commits"] == 0
        assert source.read_bytes() == before_source
        assert target.read_bytes() == before_target
    if not in_place:
        assert source.read_bytes() == before_source
    assert not list(tmp_path.glob(".*.staged.aseprite"))


def observed_cli(
    tmp_path: Path, operation: str, request: dict, case: str = "success"
) -> tuple[dict, dict]:
    cli = shutil.which("spa")
    assert cli, "run tests in an installed SPA environment"
    observations_path = tmp_path / "observations.json"
    run = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "fixtures" / "observe_persistence_cli.py"),
            case,
            str(observations_path),
            cli,
            *operation.split(),
            "--input-json",
            json.dumps(request),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.stdout, run.stderr
    return json.loads(run.stdout), json.loads(observations_path.read_text())


def test_cel_and_motion_plan_saves_only_after_all_steps(tmp_path: Path) -> None:
    source = fixture(tmp_path, uuids="true")
    before_source = source.read_bytes()
    outcome, observations = observed_cli(
        tmp_path,
        "plan run",
        {
            "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(tmp_path / "planned.aseprite"),
                "steps": [
                    {
                        "operation": "cel set",
                        "input": {
                            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                            "opacity": 42,
                        },
                    },
                    {"operation": "motion apply", "input": curves()},
                ],
            },
        },
    )
    assert outcome["status"] == "success", outcome
    assert outcome["persisted_reopen_verified"] is True
    assert all(
        step["result"]["persisted_reopen_verified"] is False
        for step in outcome["steps"]
    )
    assert observations == {
        "handler_invocations": 1,
        "probe_invocations": 0,
        "commits": 1,
        "saves": 1,
        "staged_opens": 2,
        "editor_restored": True,
        "owned_sprites_closed": True,
    }
    assert source.read_bytes() == before_source
