"""Installed PNG Export against a real Aseprite executable."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from jsonschema import validate
from PIL import Image

from spa.contracts import RuntimeRequest
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from spa.sprite import SPRITE_PROBE_RESOURCES
from tests.support import spa

pytestmark = pytest.mark.e2e


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source.aseprite"
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]),
        SPRITE_PROBE_RESOURCES,
    )
    fixture = Path(__file__).parent / "fixtures" / "rgb_frames.lua"
    with tempfile.TemporaryDirectory(prefix="spa-export-fixture-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={source}",
                "--script",
                str(fixture),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr
    assert source.is_file()
    return source


def test_export_frame_as_verified_visible_rgb_png(tmp_path: Path) -> None:
    source = _source(tmp_path)
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "image.png"
    request = {
        "source_sprite_file": str(source),
        "destination": {"path": str(destination), "if_exists": "fail"},
        "frame_number": 2,
        "color_mode": "preserve",
        "color_profile": "preserve",
        "transparency": "preserve",
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }

    run = spa("export", "image", "--input-json", json.dumps(request))

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(
        result, json.loads(spa("export", "image", "--schema").stdout)["result_schema"]
    )
    assert result["destination"] == request["destination"]
    assert result["frame_number"] == 2
    assert result["artifact"]["path"] == str(destination)
    assert result["artifact"]["role"] == "image"
    assert result["artifact"]["format"] == "png"
    assert result["artifact"]["media_type"] == "image/png"
    assert result["artifact"]["byte_size"] == destination.stat().st_size
    assert (
        result["artifact"]["sha256"]
        == hashlib.sha256(destination.read_bytes()).hexdigest()
    )
    with Image.open(destination) as image:
        image.load()
        assert image.size == (3, 2)
        assert image.convert("RGBA").getpixel((1, 0)) == (17, 34, 51, 128)
        assert image.convert("RGBA").getpixel((0, 0)) == (0, 0, 0, 0)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_sha
