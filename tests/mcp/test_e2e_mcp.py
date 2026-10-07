"""Installed stdio tools through real Aseprite, including native PNG content."""

import base64
import hashlib
import io
import json
import os
import shutil

import anyio
import pytest
from jsonschema import validate
from mcp import Client, StdioServerParameters
from PIL import Image

from tests.export.support import export_image_request
from tests.support import spa

pytestmark = pytest.mark.e2e


def test_installed_mcp_workflow_matches_cli_and_delivers_png(tmp_path):
    executable = shutil.which("spa-mcp")
    assert executable
    aseprite = os.environ["SPA_TEST_ASEPRITE"]
    manifest_run = spa("schema", "--aseprite", aseprite)
    assert manifest_run.returncode == 0, manifest_run.stdout
    manifest = json.loads(manifest_run.stdout)
    entries = {entry["operation"]: entry for entry in manifest["operations"]}
    source = tmp_path / "mcp.aseprite"
    destination = tmp_path / "mcp.png"

    async def exercise():
        params = StdioServerParameters(
            command=executable, args=["--aseprite", aseprite]
        )
        async with Client(
            params, mode="2026-07-28", read_timeout_seconds=120
        ) as client:
            assert client.protocol_version == "2026-07-28"
            discovered = await client.session.send_discover("2026-07-28")
            assert "2026-07-28" in discovered["supportedVersions"]
            listed = await client.list_tools()
            assert len(listed.tools) == len(entries)
            for tool in listed.tools:
                entry = entries[tool.description]
                assert tool.input_schema == entry["request_schema"]
                assert tool.output_schema == entry["result_schema"]

            async def call(name, request):
                result = await client.call_tool(name, request)
                assert not result.is_error, result.model_dump_json()
                payload = result.structured_content
                assert json.loads(result.content[0].text) == payload
                validate(payload, entries[payload["operation"]]["result_schema"])
                return result

            schema = await call("schema", {})
            assert (
                schema.structured_content["capability_gaps"]
                == manifest["capability_gaps"]
            )
            for entry in schema.structured_content["operations"]:
                assert (
                    entry["failure_schema"]
                    == entries[entry["operation"]]["failure_schema"]
                )
            await call(
                "sprite_create",
                {
                    "target_sprite_file": str(source),
                    "width": 3,
                    "height": 2,
                    "color_mode": "rgb",
                    "overwrite": False,
                    "initial_layer": {
                        "kind": "background",
                        "background_color": {
                            "red": 17,
                            "green": 34,
                            "blue": 51,
                            "alpha": 255,
                        },
                    },
                },
            )
            inspected = await call(
                "sprite_get",
                {"sprite_file": str(source), "inspection_scope": ["layers", "cels"]},
            )
            assert inspected.structured_content["metadata"]["width"] == 3
            await call(
                "sprite_validate",
                {
                    "sprite_file": str(source),
                    "expected": {
                        "width": 3,
                        "height": 2,
                        "color_mode": "rgb",
                        "frame_count": 1,
                    },
                },
            )
            exported = await call(
                "export_image", export_image_request(source, destination)
            )
            images = [part for part in exported.content if part.type == "image"]
            assert len(images) == 1
            assert images[0].mime_type == "image/png"
            encoded = base64.b64decode(images[0].data, validate=True)
            artifact = exported.structured_content["artifact"]
            assert encoded == destination.read_bytes()
            assert len(encoded) == artifact["byte_size"]
            assert hashlib.sha256(encoded).hexdigest() == artifact["sha256"]
            with Image.open(io.BytesIO(encoded)) as image:
                assert image.size == (3, 2)
                assert [
                    image.convert("RGBA").getpixel((x, y))
                    for y in range(2)
                    for x in range(3)
                ] == [(17, 34, 51, 255)] * 6
            bad = await client.call_tool("version", {"unexpected": True})
            assert bad.is_error and bad.structured_content is None
            validate(
                json.loads(bad.content[0].text),
                entries["spa version"]["failure_schema"],
            )

    anyio.run(exercise)
    # An independent CLI process reopens the persisted native file after MCP exits.
    reopened = spa(
        "sprite",
        "get",
        "--aseprite",
        aseprite,
        "--input-json",
        json.dumps(
            {"sprite_file": str(source), "inspection_scope": ["layers", "cels"]}
        ),
    )
    assert reopened.returncode == 0, reopened.stdout
    assert json.loads(reopened.stdout)["metadata"]["height"] == 2


def test_installed_legacy_handshake_and_typed_failure():
    async def exercise():
        params = StdioServerParameters(
            command=shutil.which("spa-mcp"),
            args=["--aseprite", os.environ["SPA_TEST_ASEPRITE"]],
        )
        async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
            assert client.protocol_version == "2025-11-25"
            listing = await client.list_tools()
            assert any(tool.name == "sprite_create" for tool in listing.tools)
            good = await client.call_tool("version", {})
            assert not good.is_error
            assert good.structured_content["operation"] == "spa version"
            bad = await client.call_tool("version", {"unexpected": True})
            assert bad.is_error and bad.structured_content is None
            assert json.loads(bad.content[0].text)["code"] == "invalid_request"

    anyio.run(exercise)
