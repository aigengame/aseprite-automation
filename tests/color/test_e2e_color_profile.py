"""Color Profile commands preserve or transform native stored color facts."""

import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


def _native(runtime, source: Path, **params: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="spa-profile-test-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        arguments = [str(prepared.executable), "--batch"]
        for key, value in {"source": str(source), **params}.items():
            arguments.extend(["--script-param", f"{key}={value}"])
        result = subprocess.run(
            [
                *arguments,
                "--script",
                str(Path(__file__).parent / "fixtures/profile_sprite.lua"),
            ],
            env=prepared.environment,
            text=True,
            capture_output=True,
            check=False,
        )
    assert result.returncode == 0, process_diagnostics(result)
    return json.loads(result.stdout)


def _run(command: str, source: Path, target: Path, profile: dict, **extra: object):
    result = spa(
        "sprite",
        command,
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": source == target,
                "overwrite": True,
                "profile": profile,
                **extra,
            }
        ),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


def test_assign_none_preserves_stored_colors_and_persists_profile(
    tmp_path: Path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    before = _native(runtime, source, action="create")
    original = source.read_bytes()
    code, result = _run("assign-color-profile", source, target, {"kind": "none"})
    assert code == 0, result
    assert result["source_profile"]["kind"] == "srgb"
    assert result["requested_profile"]["kind"] == "none"
    assert result["effective_profile"]["kind"] == "none"
    assert result["profile_changed"] is True
    assert result["persisted_reopen_verified"] is True
    assert not any(item["changed"] for item in result["images"] + result["palettes"])
    after = _native(runtime, target, action="observe")
    assert _encoded_profile(target) == "none"
    assert after["pixels"] == before["pixels"]
    assert after["entries"] == before["entries"]
    assert source.read_bytes() == original


def _encoded_profile(path: Path) -> str:
    data = path.read_bytes()
    offset = 144
    frame_end = 128 + struct.unpack_from("<I", data, 128)[0]
    while offset < frame_end:
        size, kind = struct.unpack_from("<IH", data, offset)
        if kind == 0x2007:
            return {0: "none", 1: "srgb", 2: "icc"}[
                struct.unpack_from("<H", data, offset + 6)[0]
            ]
        offset += size
    return "none"
