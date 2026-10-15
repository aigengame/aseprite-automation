"""Invocation deadline and diagnostics with controlled process timing."""

import os
import signal
import subprocess
import sys
import time
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
        from spa.adapters.aseprite import windows_capture

        children = []
        waits = []
        clock = 0.0
        started = time.monotonic()
        capture = windows_capture.capture

        def monotonic():
            assert time.monotonic() - started < 10, "child did not close its pipes"
            return clock

        def start(*args, **kwargs):
            child = subprocess.Popen(*args, stdin=subprocess.PIPE, **kwargs)
            children.append(child)
            native_wait = child.wait

            def wait(timeout=None):
                waits.append(timeout)
                return native_wait(timeout=timeout)

            monkeypatch.setattr(child, "wait", wait)
            return child

        def capture_eof(*args):
            nonlocal clock
            result = capture(*args)
            assert result == (False, False), "the live child must reach both EOFs"
            clock = 0.75
            return result

        monkeypatch.setattr(aseprite, "time", SimpleNamespace(monotonic=monotonic))
        monkeypatch.setattr(
            windows_capture,
            "time",
            SimpleNamespace(monotonic=monotonic, sleep=time.sleep),
        )
        monkeypatch.setattr(windows_capture, "capture", capture_eof)
        monkeypatch.setattr(
            aseprite,
            "subprocess",
            SimpleNamespace(
                Popen=start,
                PIPE=subprocess.PIPE,
                TimeoutExpired=subprocess.TimeoutExpired,
            ),
        )
        try:
            with pytest.raises(RuntimeIssue) as observed:
                aseprite._run(
                    [
                        # A Windows venv redirector keeps pipe writers open.
                        sys._base_executable,
                        "-c",
                        (
                            "import os; os.write(1,b'before timeout'); "
                            "os.write(2,b'diagnostic'); os.close(1); os.close(2); "
                            "os.read(0,1)"
                        ),
                    ],
                    os.environ.copy(),
                    1,
                    Path(sys._base_executable),
                )
            assert observed.value.kind == "deadline"
            assert observed.value.diagnostics.stdout == "before timeout"
            assert observed.value.diagnostics.stderr == "diagnostic"
            assert waits == [0.25, None]
            child = children[0]
            assert child.poll() == observed.value.diagnostics.exit_status
            assert child.stdout.closed and child.stderr.closed
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait()
                child.stdin.close()
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
