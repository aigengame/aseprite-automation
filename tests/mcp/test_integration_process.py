"""CLI process failure and cancellation do not masquerade as SPA outcomes."""

import json
import os
import subprocess
import sys

import anyio
import pytest

from spa.access.mcp.cli import Cli


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
def test_cancellation_stops_cli_and_its_native_child(tmp_path):
    marker = tmp_path / "child-pids.json"
    program = tmp_path / "waiting-cli.py"
    program.write_text(f"""
import json, os, subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
with open({str(marker)!r}, 'w') as target:
    json.dump([os.getpid(), child.pid], target)
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
