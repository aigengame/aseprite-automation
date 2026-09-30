"""Native evidence gates standalone Cel and Motion Target Commit and cleanup."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.motion.test_e2e_motion import curves, fixture

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("operation", ["cel set", "motion apply"])
@pytest.mark.parametrize("in_place", [False, True])
@pytest.mark.parametrize(
    "case",
    [
        "success",
        "probe",
        "invocation",
        "evidence",
        "postcondition",
        "identity",
        "commit",
    ],
)
def test_standalone_completion_gates_commit_and_cleans_staging(
    tmp_path: Path, operation: str, in_place: bool, case: str
) -> None:
    source = fixture(tmp_path, uuids="true")
    target = source if in_place else tmp_path / "target.aseprite"
    if not in_place:
        target.write_bytes(b"existing Target")
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
    cli = shutil.which("spa")
    assert cli, "run tests in an installed SPA environment"
    report = tmp_path / "completion.json"
    run = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "fixtures" / "observe_mutation_completion.py"),
            case,
            str(report),
            cli,
            *operation.split(),
            "--input-json",
            json.dumps(request),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.stdout, run.stderr
    outcome, observed = json.loads(run.stdout), json.loads(report.read_text())
    if case == "success":
        assert run.returncode == 0, outcome
        assert outcome["persisted_reopen_verified"] is True
        assert observed["commits"] == 1
        saved = target.read_bytes()
        assert saved != before_target
        assert outcome["target_commit"] == {
            "target_sprite_file": str(target),
            "byte_size": len(saved),
            "sha256": hashlib.sha256(saved).hexdigest(),
        }
    else:
        assert run.returncode == 1, outcome
        assert observed["commits"] == 0
        assert source.read_bytes() == before_source
        assert target.read_bytes() == before_target
        if case in ("probe", "invocation"):
            assert outcome["code"] == "process_failed"
            assert outcome["category"] == "execution"
            assert outcome["details"]["exit_status"] == 13
        elif case in ("evidence", "postcondition"):
            assert outcome["code"] == "kernel_response_invalid"
            assert outcome["category"] == "kernel_protocol"
        else:
            assert outcome["code"] == "target_commit_failed"
            assert outcome["category"] == "execution"
            assert outcome["details"]["reason"] == (
                "source_target_identity_changed"
                if case == "identity"
                else "replace_failed"
            )
            if case == "identity":
                assert outcome["message"] == (
                    "Source/Target publication identity changed before Target Commit"
                    if operation == "cel set"
                    else "Source/Target identity changed before Target Commit"
                )
    if not in_place:
        assert source.read_bytes() == before_source
    expected_events = ["probe"]
    if case != "probe":
        expected_events.extend(["identity", "stage", "invoke"])
        if case in ("success", "identity", "commit"):
            expected_events.append("identity")
        if case in ("success", "commit"):
            expected_events.append("commit")
        expected_events.append("discard")
        assert observed["discarded"] is True
        assert not Path(observed["staged"]).exists()
    assert observed["events"] == expected_events
    assert observed["native_invocations"] == int(case not in ("probe", "invocation"))
    assert not list(tmp_path.glob(".*.staged.aseprite"))
