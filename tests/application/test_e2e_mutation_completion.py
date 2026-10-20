"""Native evidence gates standalone mutation Target Commit and cleanup."""

import hashlib
import os
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.application.support import (
    OPERATIONS,
    assert_completion_trace,
    completion_request,
    observe_completion,
)
from tests.support import motion_sprite

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("in_place", [False, True])
@pytest.mark.parametrize(
    "case", ["success", "evidence", "postcondition", "identity", "commit"]
)
def test_standalone_completion_gates_commit_and_cleans_staging(
    runtime: RuntimeObservation,
    tmp_path: Path,
    operation: str,
    in_place: bool,
    case: str,
) -> None:
    source = motion_sprite(runtime, tmp_path, uuids="true")
    target = source if in_place else tmp_path / "target.aseprite"
    if not in_place:
        target.write_bytes(b"existing Target")
    before_source, before_target = source.read_bytes(), target.read_bytes()
    request = completion_request(
        operation, os.environ["SPA_TEST_ASEPRITE"], source, target, in_place
    )
    run, outcome, observed = observe_completion(case, tmp_path, operation, request)
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
        if case in ("evidence", "postcondition"):
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
                assert outcome["message"] == {
                    "motion apply": "Source/Target identity changed before Target Commit",
                    "image replace": "Source/Target identity changed",
                    "paint composite": "Source/Target identity changed",
                }.get(
                    operation,
                    "Source/Target publication identity changed before Target Commit",
                )
    if not in_place:
        assert source.read_bytes() == before_source
    assert_completion_trace(observed, operation, case, tmp_path)
