"""Candidate Paint tools stay unavailable until their native seams are verified."""

import json
from pathlib import Path

from tests.support import fake_probe_response, spa


def test_unverified_native_paint_candidates_have_independent_manifest_gaps(
    tmp_path: Path,
) -> None:
    binary = fake_probe_response(
        tmp_path,
        json.dumps(
            {
                "kernel_protocol_version": 1,
                "status": "ok",
                "aseprite_version": "test-runtime",
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
    assert all(gap["aseprite_version"] == "test-runtime" for gap in gaps.values())
    assert all(gap["evidence"] for gap in gaps.values())
    assert all("1.3.18.5" not in gap["evidence"] for gap in gaps.values())
    assert all(gap in manifest["capability_gaps"] for gap in gaps.values())
    supported = set(info_result["supported_capabilities"])
    assert expected.isdisjoint(supported)
    assert {"spa paint line", "spa paint rectangle", "spa paint ellipse"} <= supported
    for command in expected:
        _, _, tool = command.split()
        attempt = spa("paint", tool, "--schema")
        assert attempt.returncode == 2
        assert json.loads(attempt.stdout)["code"] == "invalid_request"
