"""Public Tile inspection preserves existing native content and identities."""

from pathlib import Path

import pytest

from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


def test_lists_multiple_tilesets_and_shared_layer_bindings_without_repair(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    fixture(source, runtime)
    original = source.read_bytes()
    code, result = run("tileset", "list", sprite_file=str(source))
    assert code == 0, result
    assert result["complete"] is True
    terrain = next(item for item in result["tilesets"] if item["name"] == "terrain")
    assert terrain["tileset_index"] == 1
    assert terrain["tile_count"] == 5
    assert terrain["base_index"] == 1
    assert terrain["grid"] == {
        "origin": {"x": 0, "y": 0},
        "tile_size": {"width": 2, "height": 3},
    }
    assert {item["name"] for item in terrain["layers"]} == {"map", "shared"}
    assert result["tilesets"][-1]["layers"] == []
    assert source.read_bytes() == original
