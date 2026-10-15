"""Invocation deadline and diagnostics with controlled process timing."""

import os
import signal
import subprocess
import sys
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


def test_closed_streams_keep_the_deadline_and_captured_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name == "nt":
        with pytest.raises(RuntimeIssue) as observed:
            aseprite._run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import os,time; time.sleep(.6); os.write(1,b'before timeout'); "
                        "os.write(2,b'diagnostic'); os.close(1); os.close(2); time.sleep(1)"
                    ),
                ],
                os.environ.copy(),
                1,
                Path(sys.executable),
            )
        assert observed.value.kind == "deadline"
        assert observed.value.diagnostics.stdout == "before timeout"
        assert observed.value.diagnostics.stderr == "diagnostic"
        assert observed.value.diagnostics.exit_status is not None
        return
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
