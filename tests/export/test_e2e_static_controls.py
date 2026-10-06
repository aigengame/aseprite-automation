"""Static export controls through the public CLI and independent PNG decoding."""

import json
from pathlib import Path

import pytest
from PIL import Image

from tests.export.support import export_image_request as _request
from tests.export.support import source_sprite
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


def test_export_fills_transparency_with_explicit_background(tmp_path: Path):
    source = source_sprite(tmp_path, "rgb_profile_alpha.lua", alpha="transparent")
    original = source.read_bytes()
    destination = tmp_path / "opaque.png"
    request = _request(source, destination) | {
        "transparency": {
            "kind": "background",
            "background_color": {
                "kind": "rgba",
                "red": 21,
                "green": 43,
                "blue": 65,
                "alpha": 255,
            },
        }
    }
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["effective_background"] is True
    assert result["alpha_channel"]["minimum"] == 255
    with Image.open(destination) as image:
        assert (
            list(image.convert("RGBA").get_flattened_data()) == [(21, 43, 65, 255)] * 2
        )
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


def test_export_changes_grayscale_to_rgb_without_changing_visible_channels(
    tmp_path: Path,
):
    source = source_sprite(
        tmp_path, "rgb_profile_alpha.lua", mode="grayscale", profile="none"
    )
    destination = tmp_path / "rgb.png"
    request = _request(source, destination) | {
        "export_image_area": {"kind": "canvas"},
        "layer_composition": {"mode": "visible"},
        "composition_color_mode": "preserve",
        "color_mode": {
            "source_color_mode": "grayscale",
            "target": {"color_mode": "rgb"},
        },
    }
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["source_color_mode"] == "grayscale"
    assert result["color_mode"] == "rgb"
    with Image.open(destination) as image:
        assert image.convert("RGBA").getpixel((0, 0)) == (90, 90, 90, 127)


def test_export_imports_palette_before_index_mapping(tmp_path: Path):
    source = source_sprite(tmp_path, "rgb_profile_alpha.lua", alpha="opaque")
    original = source.read_bytes()
    palette = tmp_path / "colors.gpl"
    palette.write_text(
        "GIMP Palette\nChannels: RGBA\nName: export\n#\n0 0 0 0 clear\n11 22 33 255 first\n44 55 66 255 second\n"
    )
    destination = tmp_path / "mapped.png"
    request = _request(source, destination) | {
        "color_mode": {
            "source_color_mode": "rgb",
            "target": {
                "color_mode": "indexed",
                "rgb_map_algorithm": "rgb5a3",
                "color_best_fit_criteria": "rgb",
                "dithering": {"algorithm": "none"},
            },
        },
        "palette_preparation": {
            "kind": "import",
            "palette_file": {"format": "gpl", "path": str(palette)},
        },
    }
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["color_mode"] == "indexed"
    with Image.open(destination) as image:
        assert image.mode == "P"
        assert list(image.get_flattened_data()) == [1, 2]
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (11, 22, 33, 255),
            (44, 55, 66, 255),
        ]
    assert source.read_bytes() == original
