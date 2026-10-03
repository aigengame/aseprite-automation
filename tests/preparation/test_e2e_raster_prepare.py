"""Prepare selected raster bytes through the installed CLI and native owners."""

import hashlib
import json
import os

import pytest
from PIL import Image

from tests.preparation.support import specification
from tests.support import spa

pytestmark = pytest.mark.e2e


def test_prepare_rgba_thresholds_aligns_and_publishes(tmp_path):
    source, target = tmp_path / "input.png", tmp_path / "prepared.png"
    pixels = [
        (180, 70, 30, 255),
        (30, 90, 180, 255),
        (44, 11, 66, 0),
        (180, 70, 30, 127),
        (30, 90, 180, 128),
        (0, 0, 0, 0),
    ]
    image = Image.new("RGBA", (3, 2))
    image.putdata(pixels)
    image.save(source)
    original = source.read_bytes()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "raster_file": str(source),
        "intent": {"kind": "initial"},
        "specification": specification(),
        "destination": {"path": str(target), "if_exists": "fail"},
    }
    run = spa("raster", "prepare", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    facts = result["reproduction"]
    assert facts["source_identity"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert facts["geometry"]["offset"] == {"x": 1, "y": 1}
    assert facts["geometry"]["anchors"] == [{"name": "foot", "x": 2, "y": 3}]
    expected = [(0, 0, 0, 0)] * 20
    expected[6], expected[7], expected[12] = pixels[0], pixels[1], (30, 90, 180, 255)
    with Image.open(target) as prepared:
        assert prepared.mode == "RGBA"
        assert prepared.info["srgb"] == 0
        assert "icc_profile" not in prepared.info
        assert list(prepared.get_flattened_data()) == expected
    assert source.read_bytes() == original
    assert (
        result["artifact"]["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    )
    assert not list(tmp_path.glob(".*.staged*"))
