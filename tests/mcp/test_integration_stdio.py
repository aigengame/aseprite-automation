"""Public MCP wire behavior with a controlled external CLI process."""

import json
import os
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from mcp import Client, StdioServerParameters

from tests.native_entry import python_entry
from tests.support import process_diagnostics


@pytest.fixture
def cli(tmp_path):
    request = {
        "type": "object",
        "properties": {"value": {}},
        "additionalProperties": False,
    }
    result = {
        "type": "object",
        "properties": {
            "status": {"const": "success"},
            "operation": {"const": "spa echo"},
            "value": {},
        },
        "required": ["status", "operation", "value"],
    }
    manifest = {
        "status": "success",
        "operation": "spa schema",
        "operations": [
            {
                "operation": "spa echo",
                "help_summary": "Echo a JSON value without changing its content.",
                "execution_kind": "read",
                "side_effects": [],
                "request_schema": request,
                "result_schema": result,
                "failure_schema": {
                    "type": "object",
                    "required": ["code", "diagnostics"],
                },
            }
        ],
    }

    def write_cli(*, output=None, exit_status=0, stderr=""):
        script = f"""import json, sys
request = json.load(sys.stdin)
if sys.argv[1] == 'schema':
    print({json.dumps(json.dumps(manifest))})
else:
    output = {output!r}
    if output is None:
        output = json.dumps({{"status": "success", "operation": "spa echo", "value": request.get("value")}})
    print(output)
    stderr = {stderr!r}
    if stderr:
        print(stderr, file=sys.stderr)
    sys.exit({exit_status})
"""
        # SPA writes UTF-8 to the CLI; a UTF-8 locale makes this prelude a no-op.
        return python_entry(
            tmp_path,
            "spa-fixture",
            "import sys\n"
            "for stream in (sys.stdin, sys.stdout, sys.stderr):\n"
            "    stream.reconfigure(encoding='utf-8', errors=stream.errors)\n" + script,
        )

    return write_cli, manifest


def parameters(cli: Path, **env):
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", "from spa.mcp_bootstrap import main; main()", "--spa", str(cli)],
        env={**os.environ, **env},
    )


def test_cli_fixture_executes_requests_and_retains_diagnostics(cli):
    write_cli, manifest = cli
    program = write_cli(exit_status=2, stderr="fixture warning")
    discovery = subprocess.run(
        [str(program), "schema", "--input-json", "-", "--json"],
        input=b"{}",
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert discovery.returncode == 0, process_diagnostics(discovery)
    assert discovery.stderr == b"", process_diagnostics(discovery)
    assert json.loads(discovery.stdout.decode("utf-8")) == manifest, (
        process_diagnostics(discovery)
    )

    request = {"value": {"unicode": "像素", "nested": [1, False, None]}}
    called = subprocess.run(
        [str(program), "echo", "--input-json", "-", "--json"],
        input=json.dumps(request, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert called.returncode == 2, process_diagnostics(called)
    assert json.loads(called.stdout.decode("utf-8")) == {
        "status": "success",
        "operation": "spa echo",
        "value": request["value"],
    }, process_diagnostics(called)
    assert called.stderr.decode("utf-8").strip() == "fixture warning", (
        process_diagnostics(called)
    )


@pytest.mark.parametrize(
    "mode,protocol", [("2026-07-28", "2026-07-28"), ("legacy", "2025-11-25")]
)
def test_stdio_projects_manifest_and_preserves_request_and_result(cli, mode, protocol):
    write_cli, manifest = cli
    program = write_cli()

    async def exercise():
        async with Client(
            parameters(program), mode=mode, read_timeout_seconds=15
        ) as client:
            assert client.protocol_version == protocol
            if mode != "legacy":
                discovered = await client.session.send_discover(protocol)
                assert protocol in discovered["supportedVersions"]
            listed = await client.list_tools()
            assert [tool.name for tool in listed.tools] == ["echo"]
            tool = listed.tools[0]
            entry = manifest["operations"][0]
            assert tool.description == entry["help_summary"]
            assert tool.input_schema == entry["request_schema"]
            assert tool.output_schema == entry["result_schema"]
            assert tool.meta["spa"]["execution_kind"] == "read"
            assert tool.meta["spa"]["side_effects"] == []
            value = {"unicode": "像素", "nested": [1, False, None]}
            called = await client.call_tool("echo", {"value": value})
            assert not called.is_error
            expected = {"status": "success", "operation": "spa echo", "value": value}
            assert called.structured_content == expected
            assert json.loads(called.content[0].text) == expected

    anyio.run(exercise)


def test_nonzero_cli_failure_is_lossless_and_has_no_success_content(cli):
    write_cli, _ = cli
    failure = {
        "status": "failure",
        "operation": "spa echo",
        "code": "invalid_request",
        "diagnostics": {"stderr": "native detail", "exit_status": 42},
    }
    program = write_cli(output=json.dumps(failure), exit_status=2)

    async def exercise():
        async with Client(parameters(program), mode="2026-07-28") as client:
            called = await client.call_tool("echo", {"value": "bad"})
            assert called.is_error
            assert called.structured_content is None
            assert json.loads(called.content[0].text) == failure

    anyio.run(exercise)


@pytest.mark.parametrize(
    "output", ["not json", '{"status":"success","operation":"spa echo","wrong":1}']
)
def test_unusable_cli_output_retains_diagnostics(cli, output):
    write_cli, _ = cli
    program = write_cli(output=output, stderr="native warning")

    async def exercise():
        async with Client(parameters(program), mode="2026-07-28") as client:
            called = await client.call_tool("echo", {})
            assert called.is_error
            assert called.structured_content is None
            error = json.loads(called.content[0].text)["adapter_error"]
            assert error["stdout"].strip() == output
            assert error["stderr"].strip() == "native warning"
            assert error["exit_status"] == 0

    anyio.run(exercise)
