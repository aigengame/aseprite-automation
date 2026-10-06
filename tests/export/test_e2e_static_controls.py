"""Static export controls through the public CLI and independent PNG decoding."""

import json
from pathlib import Path

import pytest
from PIL import Image

from tests.export.support import source_sprite
from tests.export.test_e2e_export_image import _request
from tests.support import spa

pytestmark = pytest.mark.e2e


def test_export_selected_hidden_layer_and_canvas_rectangle(tmp_path: Path):
    source = source_sprite(tmp_path, "group_composition.lua")
    original = source.read_bytes()
    destination = tmp_path / "component.png"
    request = _request(source, destination) | {
        "export_image_area": {
            "kind": "rectangle",
            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
        },
        "layer_composition": {
            "mode": "include",
            "layers": [{"layer_name": "hidden red"}],
        },
        "composition_color_mode": "preserve",
    }
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert (
        result["export_image_area"]["rectangle"]
        == request["export_image_area"]["rectangle"]
    )
    assert result["source_color_mode"] == result["color_mode"] == "rgb"
    assert result["composition_color_mode"] == "preserve"
    with Image.open(destination) as image:
        assert image.size == (1, 1)
        assert image.convert("RGBA").getpixel((0, 0)) == (255, 0, 0, 255)
    assert source.read_bytes() == original


def test_export_assign_none_preserves_pixels_and_source(tmp_path: Path):
    source = source_sprite(tmp_path, "rgb_profile_alpha.lua", profile="srgb")
    original = source.read_bytes()
    destination = tmp_path / "assigned.png"
    request = _request(source, destination) | {
        "export_image_area": {"kind": "canvas"},
        "layer_composition": {"mode": "visible"},
        "composition_color_mode": "preserve",
        "color_profile": {"kind": "assign", "profile": {"kind": "none"}},
    }
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["color_profile"] == "none"
    with Image.open(destination) as image:
        assert image.convert("RGBA").getpixel((0, 0)) == (11, 22, 33, 127)
        assert "icc_profile" not in image.info and "srgb" not in image.info
    assert source.read_bytes() == original
