"""Helpers shared across test ownership areas."""

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from spa.ports import (
    KernelInvocationResult,
    OperationServices,
    PackagedHandler,
    RuntimeObservation,
    RuntimeProbe,
    TargetCommitObservation,
)


class _UnusedTargetFiles:
    def staged_path(self, _target: Path) -> Path:
        raise AssertionError("test did not configure Target Files")

    def commit(
        self, _staged: Path, _target: Path, *, overwrite: bool
    ) -> TargetCommitObservation:
        raise AssertionError("test did not configure Target Files")

    def discard(self, _staged: Path) -> None:
        return None


def operation_services(probe: RuntimeProbe) -> OperationServices:
    """Supply explicit unused adapters to tests that exercise probe-only Operations."""

    def invoke(
        _observation: RuntimeObservation,
        _handler: PackagedHandler,
        _payload: dict[str, Any],
        _timeout: float,
    ) -> KernelInvocationResult:
        raise AssertionError("test did not configure a Kernel invoker")

    return OperationServices(probe, invoke, _UnusedTargetFiles())


def spa(
    *args: str,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
    executable: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the installed SPA command from the active project environment."""
    selected = str(executable) if executable is not None else shutil.which("spa")
    assert selected, "run tests in an installed SPA environment"
    return subprocess.run(
        [selected, *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
        input=stdin,
    )


def fake_aseprite(tmp_path: Path, body: str) -> Path:
    """Create a controlled executable with a macOS-style resource layout."""
    binary = tmp_path / "Aseprite.app" / "Contents" / "MacOS" / "aseprite"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    binary.chmod(0o755)
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    resource.parent.mkdir(parents=True)
    resource.write_text("<gui/>", encoding="utf-8")
    return binary


def fake_probe_response(tmp_path: Path, response: str) -> Path:
    """Create a controlled Aseprite transport that returns one probe response."""
    quoted_response = shlex.quote(response)
    return fake_aseprite(
        tmp_path,
        f"""
request=
response_file=
echo_file=
for argument in "$@"; do
  case "$argument" in
    request=*) request=${{argument#request=}};;
    response=*) response_file=${{argument#response=}};;
    echo=*) echo_file=${{argument#echo=}};;
  esac
done
cp "$request" "$echo_file"
printf '%s' {quoted_response} > "$response_file"
""",
    )
