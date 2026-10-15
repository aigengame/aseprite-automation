"""Candidate Paint tools stay unavailable until their native seams are verified."""

import json
from pathlib import Path

import pytest

from spa import SPA_BASELINE_ASEPRITE_VESION
from tests.support import fake_probe_response, spa


@pytest.mark.parametrize(
    "aseprite_version", [SPA_BASELINE_ASEPRITE_VESION, "test-runtime"]
)
def test_unavailable_paint_guidance_keeps_selected_runtime_identity(
    tmp_path: Path, aseprite_version: str
) -> None:
    binary = fake_probe_response(
        tmp_path,
        json.dumps(
            {
                "kernel_protocol_version": 1,
                "status": "ok",
                "aseprite_version": aseprite_version,
                "api_version": 41,
                "lua_version": "Lua 5.4",
                "verified_prerequisites": [
                    "aseprite_scripting",
                    "lua_file_io",
                    "aseprite_json",
                ],
                "verified_capabilities": [
                    "aseprite_runtime_introspection",
                    "aseprite_paint_line",
                    "aseprite_paint_rectangle",
                    "aseprite_paint_ellipse",
                ],
            }
        ),
    )
    info = spa("info", "--aseprite", str(binary))
    schema = spa("schema", "--aseprite", str(binary))
    assert info.returncode == schema.returncode == 0
    info_result, manifest = json.loads(info.stdout), json.loads(schema.stdout)
    expected = {f"spa paint {tool}" for tool in ("spray", "curve", "polygon", "jumble")}
    gaps = {
        gap["capability"]: gap
        for gap in info_result["capability_gaps"]
        if gap["capability"] in expected
    }
    assert set(gaps) == expected
    assert all(gap["aseprite_version"] == aseprite_version for gap in gaps.values())
    assert all(gap["reason"] for gap in gaps.values())
    assert all("SPA does not provide" in gap["reason"] for gap in gaps.values())
    assert info_result["capability_gaps"] == manifest["capability_gaps"]
    supported = set(info_result["supported_capabilities"])
    assert expected.isdisjoint(supported)
    assert expected.isdisjoint(item["operation"] for item in manifest["operations"])
    assert {"spa paint line", "spa paint rectangle", "spa paint ellipse"} <= supported
    for command in expected:
        _, _, tool = command.split()
        attempt = spa("paint", tool, "--schema")
        assert attempt.returncode == 2
        assert json.loads(attempt.stdout)["code"] == "invalid_request"
