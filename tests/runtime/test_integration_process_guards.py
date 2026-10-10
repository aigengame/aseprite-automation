"""Invocation deadline and diagnostics with controlled process timing."""

import os
import signal
import subprocess
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from spa.adapters.aseprite import aseprite
from spa.contracts.caller_script import ScriptRunRequest
from spa.contracts.ports import RuntimeIssue
from tests.support import fake_aseprite, runtime_observation

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX pipe fixture")


def test_closed_streams_keep_the_deadline_and_captured_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = fake_aseprite(tmp_path, "exit 0\n")
    observation = replace(
        runtime_observation(),
        canonical_path=str(binary),
        resource_path=str(binary.parent.parent / "Resources" / "data" / "gui.xml"),
    )
    process = Mock()
    process.poll.return_value = None

    # Output and EOF have arrived after 0.75 s of a 1 s invocation. The child
    # needs another 0.5 s to exit: only a fresh, incorrect deadline lets it finish.
    ticks = iter((0.0,))
    monkeypatch.setattr(
        aseprite, "time", SimpleNamespace(monotonic=lambda: next(ticks, 0.75))
    )

    def wait(timeout: float | None = None) -> int:
        if process.kill.called:
            return -signal.SIGKILL
        assert timeout is not None, "the live child needs a bounded wait"
        if timeout < 0.5:
            raise subprocess.TimeoutExpired("controlled child", timeout)
        return 0

    process.wait.side_effect = wait
    monkeypatch.setattr(aseprite.subprocess, "Popen", lambda *a, **kw: process)
    with ExitStack() as streams:
        for name, data in (("stdout", b"before timeout"), ("stderr", b"diagnostic")):
            reader, writer = os.pipe()
            setattr(process, name, streams.enter_context(os.fdopen(reader, "rb")))
            with os.fdopen(writer, "wb") as output:
                output.write(data)

        request = ScriptRunRequest.model_validate(
            {"script": {"kind": "inline", "code": ""}, "timeout_seconds": 1}
        )
        with pytest.raises(RuntimeIssue) as failure:
            aseprite.invoke_script(observation, request)

    assert failure.value.kind == "deadline"
    assert failure.value.diagnostics.stdout == "before timeout"
    assert failure.value.diagnostics.stderr == "diagnostic"
    assert failure.value.diagnostics.exit_status == -signal.SIGKILL
