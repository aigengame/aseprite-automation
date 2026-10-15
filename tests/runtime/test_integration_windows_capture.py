"""Windows pipe capture through the owning module with real Python children."""

import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from spa.adapters.aseprite import aseprite
from spa.adapters.aseprite.aseprite import _run
from spa.contracts.ports import RuntimeIssue

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows pipe capture")


def test_python_child_retains_status_and_both_utf8_streams() -> None:
    status, diagnostics = _run(
        [
            sys.executable,
            "-c",
            (
                "import os; os.write(1, b'output\\r\\n\\xe5\\x80\\xbc'); "
                "os.write(2, b'diagnostic\\n'); raise SystemExit(13)"
            ),
        ],
        os.environ.copy(),
        5,
        Path(sys.executable),
    )
    assert status == diagnostics.exit_status == 13
    assert diagnostics.stdout == "output\r\n值"
    assert diagnostics.stderr == "diagnostic\n"


@pytest.fixture
def owned_processes(monkeypatch):
    """Observe actual OS children and retire them if a red test fails early."""
    children = []

    def start(*args, **kwargs):
        child = subprocess.Popen(*args, **kwargs)
        children.append(child)
        return child

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
        yield children
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait()


def test_each_pipe_accepts_exactly_65536_bytes(owned_processes) -> None:
    status, diagnostics = _run(
        [
            sys.executable,
            "-c",
            "import os; os.write(1,b'x'*65536); os.write(2,b'y'*65536)",
        ],
        os.environ.copy(),
        5,
        Path(sys.executable),
    )
    assert status == diagnostics.exit_status == 0
    assert diagnostics.stdout == "x" * 65536
    assert diagnostics.stderr == "y" * 65536
    assert owned_processes[0].poll() == 0
    assert owned_processes[0].stdout.closed and owned_processes[0].stderr.closed


@pytest.mark.parametrize("descriptor", [1, 2])
def test_output_overflow_is_bounded_and_child_is_reaped(descriptor, owned_processes):
    with pytest.raises(RuntimeIssue) as observed:
        _run(
            [
                sys.executable,
                "-c",
                f"import os,time; os.write({descriptor},b'x'*65537); time.sleep(10)",
            ],
            os.environ.copy(),
            3,
            Path(sys.executable),
        )
    issue = observed.value
    assert issue.kind == "output_overflow"
    assert (
        getattr(issue.diagnostics, "stdout" if descriptor == 1 else "stderr")
        == "x" * 65536
    )
    assert issue.diagnostics.exit_status is not None
    assert owned_processes[0].poll() == issue.diagnostics.exit_status
    assert owned_processes[0].stdout.closed and owned_processes[0].stderr.closed


def test_silent_timeout_reaps_child_and_returns_bounded_diagnostics(owned_processes):
    started = time.monotonic()
    with pytest.raises(RuntimeIssue) as observed:
        _run(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            os.environ.copy(),
            0.25,
            Path(sys.executable),
        )
    assert time.monotonic() - started < 2
    issue = observed.value
    assert issue.kind == "deadline"
    assert issue.diagnostics.stdout == issue.diagnostics.stderr == ""
    assert issue.diagnostics.exit_status is not None
    assert owned_processes[0].poll() == issue.diagnostics.exit_status
    assert owned_processes[0].stdout.closed and owned_processes[0].stderr.closed


@pytest.mark.parametrize("boundary", ["set_blocking", "read"])
def test_unexpected_capture_error_reaps_child_before_workspace_cleanup(
    tmp_path,
    monkeypatch,
    owned_processes,
    boundary,
):
    original = getattr(os, boundary)

    def fail_owned_pipe(descriptor, *args):
        if (
            owned_processes
            and not owned_processes[0].stdout.closed
            and descriptor == owned_processes[0].stdout.fileno()
        ):
            raise OSError("injected pipe failure")
        return original(descriptor, *args)

    monkeypatch.setattr(os, boundary, fail_owned_pipe)
    workspace = tmp_path / "owned-workspace"
    workspace.mkdir()
    with pytest.raises(OSError, match="injected pipe failure"):
        _run(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            os.environ.copy(),
            3,
            Path(sys.executable),
            working_directory=workspace,
        )
    assert len(owned_processes) == 1
    child = owned_processes[0]
    assert child.poll() is not None
    assert child.stdout.closed and child.stderr.closed
    workspace.rmdir()
