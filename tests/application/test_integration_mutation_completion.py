"""Process failures before native evidence block standalone Target Commit."""

from pathlib import Path

import pytest

from tests.application.support import (
    OPERATIONS,
    assert_completion_trace,
    completion_request,
)
from tests.support import observe_cli, probe_only_aseprite


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("in_place", [False, True])
@pytest.mark.parametrize("case", ["probe", "invocation"])
def test_standalone_completion_gates_commit_and_cleans_staging(
    tmp_path: Path, operation: str, in_place: bool, case: str
) -> None:
    # The observer injects each process failure before a Kernel call, and the
    # probe-only Aseprite refuses a Kernel call that gets through.
    aseprite = probe_only_aseprite(tmp_path)
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"original Source")
    target = source if in_place else tmp_path / "target.aseprite"
    if not in_place:
        target.write_bytes(b"existing Target")
    before_source, before_target = source.read_bytes(), target.read_bytes()
    request = completion_request(operation, source, target, in_place)
    run, outcome, observed = observe_cli(
        case,
        operation,
        request,
        tmp_path / "completion.json",
        seam="invoke",
        aseprite=aseprite,
    )
    assert run.returncode == 1, outcome
    assert outcome["code"] == "process_failed"
    assert outcome["category"] == "execution"
    assert outcome["details"]["exit_status"] == 13
    assert observed["commits"] == 0
    assert source.read_bytes() == before_source
    assert target.read_bytes() == before_target
    assert_completion_trace(observed, operation, case, tmp_path)
