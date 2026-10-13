"""CLI process failure and cancellation do not masquerade as SPA outcomes."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import anyio
import pytest

from spa.access.mcp.cli import Cli
from tests.support import isolated_wheel_cli


@pytest.fixture(params=["console", "main", "wheel"])
def mcp_entry(request, tmp_path, monkeypatch) -> list[str]:
    if request.param == "main":
        return [
            sys.executable,
            "-X",
            "utf8=0",
            "-c",
            "from spa.mcp_bootstrap import main; main()",
        ]
    if request.param == "wheel":
        cli = Path(isolated_wheel_cli(tmp_path, monkeypatch))
        executable = cli.with_name("spa-mcp.exe" if os.name == "nt" else "spa-mcp")
        assert executable.is_file(), "install the candidate wheel with its MCP extra"
        return [str(executable)]
    executable = shutil.which("spa-mcp")
    assert executable, "run tests in an installed SPA MCP environment"
    return [executable]


def test_mcp_entry_early_usage_is_utf8(mcp_entry: list[str]) -> None:
    result = subprocess.run(
        [*mcp_entry, "--未知🚀"],
        input=b"",
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert "--未知🚀" in result.stderr.decode("utf-8")


@pytest.mark.parametrize("entry", ["console", "main", "wheel"])
def test_actual_spa_child_preserves_unicode_failure(entry, tmp_path, monkeypatch):
    if entry == "main":
        command = [
            sys.executable,
            "-X",
            "utf8=0",
            "-c",
            "from spa.bootstrap import main; main()",
        ]
    elif entry == "wheel":
        command = [isolated_wheel_cli(tmp_path, monkeypatch)]
    else:
        executable = shutil.which("spa")
        assert executable, "run tests in an installed SPA environment"
        command = [executable]

    async def exercise():
        outcome = await Cli(command, os.environ.copy()).invoke(
            "spa version", {"中文🚀": 1}
        )
        assert outcome.exit_status == 2
        assert outcome.stderr == ""
        assert outcome.payload["code"] == "invalid_request"
        assert outcome.payload["details"]["errors"][0]["location"] == ["中文🚀"]
        assert outcome.payload["details"]["errors"][0]["code"] == "extra_forbidden"

    anyio.run(exercise)


def test_missing_cli_fails_startup_visibly_without_protocol_stdout(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from spa.mcp_bootstrap import main; main()",
            "--spa",
            str(tmp_path / "missing-spa"),
        ],
        check=False,
        capture_output=True,
        text=True,
        input="",
        timeout=10,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert (
        "Could not start SPA" in json.loads(result.stderr)["adapter_error"]["message"]
    )


def test_missing_runtime_fails_discovery_without_an_empty_tool_surface(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from spa.mcp_bootstrap import main; main()",
            "--aseprite",
            str(tmp_path / "missing-aseprite"),
        ],
        check=False,
        capture_output=True,
        text=True,
        input="",
        timeout=10,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    error = json.loads(result.stderr)["adapter_error"]
    assert error["message"] == "SPA discovery failed"
    failure = json.loads(error["stdout"])
    assert failure["code"] == "executable_not_found"
    assert failure["diagnostics"] is not None


@pytest.mark.skipif(
    os.name != "posix", reason="process-group cleanup on supported macOS/Linux hosts"
)
@pytest.mark.parametrize("parent_exits", [False, True])
def test_cancellation_stops_cli_and_its_native_child(tmp_path, parent_exits):
    marker = tmp_path / "child-pids.json"
    program = tmp_path / "waiting-cli.py"
    program.write_text(f"""
import json, os, subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
with open({str(marker)!r}, 'w') as target:
    json.dump([os.getpid(), child.pid], target)
if not {parent_exits!r}:
    time.sleep(60)
""")

    async def exercise():
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(
                Cli([sys.executable, str(program)], os.environ.copy()).invoke,
                "spa wait",
                {},
            )
            with anyio.fail_after(5):
                while not marker.exists():
                    await anyio.sleep(0.02)
            tasks.cancel_scope.cancel()
        pids = json.loads(marker.read_text())
        with anyio.fail_after(5):
            while True:
                observed = await anyio.run_process(
                    ["ps", "-o", "stat=", "-p", ",".join(map(str, pids))], check=False
                )
                states = observed.stdout.decode().split()
                if not states or all(state.startswith("Z") for state in states):
                    break
                await anyio.sleep(0.02)

    anyio.run(exercise)
