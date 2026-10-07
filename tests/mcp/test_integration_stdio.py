"""Public MCP wire behavior with a controlled external CLI process."""

import json
import os
import sys
from pathlib import Path

import anyio
import pytest
from mcp import Client, StdioServerParameters


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
    program = tmp_path / "spa-fixture"
    program.write_text(f"""#!{sys.executable}
import json, sys
request = json.load(sys.stdin)
if sys.argv[1] == 'schema':
    print({json.dumps(json.dumps(manifest))})
else:
    print(json.dumps({{"status": "success", "operation": "spa echo", "value": request.get("value")}}))
""")
    program.chmod(0o755)
    return program, manifest


def parameters(cli: Path, **env):
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", "from spa.mcp_bootstrap import main; main()", "--spa", str(cli)],
        env={**os.environ, **env},
    )


@pytest.mark.parametrize(
    "mode,protocol", [("2026-07-28", "2026-07-28"), ("legacy", "2025-11-25")]
)
def test_stdio_projects_manifest_and_preserves_request_and_result(cli, mode, protocol):
    program, manifest = cli

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
    program, _ = cli
    original = program.read_text()
    failure = {
        "status": "failure",
        "operation": "spa echo",
        "code": "invalid_request",
        "diagnostics": {"stderr": "native detail", "exit_status": 42},
    }
    program.write_text(
        original.replace(
            'print(json.dumps({"status": "success", "operation": "spa echo", "value": request.get("value")}))',
            f"print({json.dumps(json.dumps(failure))}); sys.exit(2)",
        )
    )

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
    program, _ = cli
    original = program.read_text()
    program.write_text(
        original.replace(
            'print(json.dumps({"status": "success", "operation": "spa echo", "value": request.get("value")}))',
            f'print({output!r}); print("native warning", file=sys.stderr)',
        )
    )

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
