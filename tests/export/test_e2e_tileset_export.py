"""Verified Tileset atlas and map pairs through the installed public CLI."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.aseprite.aseprite import probe
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


def request(source: Path, root: Path, **overrides: object) -> dict:
    return {
        "source_sprite_file": str(source),
        "tileset": {"tileset_name": "source"},
        "target": {"layer": {"layer_name": "map"}, "frame_number": 1},
        "rectangle": {"x": 0, "y": 0, "width": 3, "height": 1},
        "columns": 3,
        "image": {"path": str(root / "atlas.png"), "if_exists": "fail"},
        "metadata": {"path": str(root / "map.json"), "if_exists": "fail"},
        **overrides,
    }


def test_export_full_keyed_tileset_and_one_map_region(tmp_path: Path, runtime) -> None:
    source = tmp_path / "source.aseprite"
    fixture(source, runtime, script="tileset_lifecycle.lua")
    before = source.read_bytes()
    code, result = run("export", "tileset", **request(source, tmp_path))
    assert code == 0, result
    assert source.read_bytes() == before
    assert [item["role"] for item in result["artifacts"]] == [
        "tileset-image",
        "map-data",
    ]
    metadata = json.loads((tmp_path / "map.json").read_text())
    assert metadata == result["map"]
    assert metadata["tileset"]["base_index"] == 11
    assert metadata["tilemap"]["position"] == {"x": -3, "y": 7}
    assert [item.get("tile_key") for item in metadata["atlas"]["tiles"]] == [
        None,
        "a",
        "b",
        "unused",
    ]
    snapshot = metadata["snapshot"]
    assert snapshot["complete"] is True
    assert snapshot["default"] == {"kind": "empty"}
    assert [entry["tile_x"] for entry in snapshot["entries"]] == [0, 1]
    assert snapshot["entries"][0]["placement"] == {
        "kind": "tile",
        "tile_index": 1,
        "tile_key": "a",
        "flip_x": True,
        "flip_y": True,
        "flip_diagonal": True,
    }
    with Image.open(tmp_path / "atlas.png") as image:
        assert image.size == (6, 6)
        rgba = image.convert("RGBA")
        assert [
            rgba.getpixel(point) for point in [(0, 0), (2, 0), (4, 0), (0, 3), (2, 3)]
        ] == [
            (0, 0, 0, 0),
            (21, 30, 40, 255),
            (22, 30, 40, 255),
            (23, 30, 40, 255),
            (0, 0, 0, 0),
        ]
