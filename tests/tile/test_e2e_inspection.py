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


def test_exact_tileset_and_tile_queries_keep_unkeyed_content_readable(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    fixture(source, runtime, base_index=10)
    original = source.read_bytes()
    code, result = run(
        "tileset", "get", sprite_file=str(source), target={"tileset_name": "terrain"}
    )
    assert code == 0, result
    assert [tile["tile_key"] for tile in result["tiles"]] == [
        None,
        "red",
        "green",
        None,
        "red",
    ]
    assert [tile["display_index"] for tile in result["tiles"]] == [9, 10, 11, 12, 13]
    code, tile = run(
        "tileset",
        "tile",
        "get",
        sprite_file=str(source),
        target={"layer": {"layer_name": "map"}},
        tile={"tile_index": 3},
    )
    assert code == 0, tile
    assert tile["tile"]["tile_key"] is None
    assert tile["snapshot"]["rectangle"] == {"x": 0, "y": 0, "width": 2, "height": 3}
    assert tile["snapshot"]["rows"][0][0]["color"]["red"] == 120
    for address, failure in [
        ({"tile_key": "red"}, "tile_key_ambiguous"),
        ({"tile_key": "unknown"}, "tile_key_missing"),
        ({"tile_index": 100}, "tile_index_out_of_bounds"),
    ]:
        code, rejected = run(
            "tileset",
            "tile",
            "get",
            sprite_file=str(source),
            target={"tileset_index": 1},
            tile=address,
        )
        assert code != 0 and rejected["code"] == failure, rejected
    code, checked = run(
        "tileset", "validate", sprite_file=str(source), target={"tileset_index": 1}
    )
    assert code == 0 and checked["valid"] is False, checked
    assert {finding["code"] for finding in checked["findings"]} == {
        "tile_key_missing",
        "tile_key_duplicate",
    }
    assert source.read_bytes() == original


def test_tilemap_region_is_complete_sparse_and_uses_cel_local_coordinates(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    fixture(source, runtime)
    target = {"layer": {"layer_name": "map"}, "frame_number": 1}
    code, topology = run("tilemap", "get", sprite_file=str(source), target=target)
    assert code == 0, topology
    assert topology["snapshot"] is None
    assert topology["tilemap"]["canvas_coverage"] == {
        "x": -5,
        "y": 7,
        "width": 6,
        "height": 6,
    }
    assert topology["tilemap"]["effective_grid"]["origin"] == {"x": -5, "y": 7}
    rectangle = {"x": 0, "y": 0, "width": 3, "height": 2}
    code, result = run(
        "tilemap", "get", sprite_file=str(source), target=target, rectangle=rectangle
    )
    assert code == 0, result
    snapshot = result["snapshot"]
    assert snapshot["rectangle"] == rectangle and snapshot["default"] == {
        "kind": "empty"
    }
    assert [
        (entry["tile_x"], entry["tile_y"], entry["placement"]["tile_index"])
        for entry in snapshot["entries"]
    ] == [(0, 0, 1), (2, 0, 2), (0, 1, 3), (2, 1, 4)]
    assert snapshot["entries"][2]["placement"] == {
        "kind": "tile",
        "tile_key": None,
        "tile_index": 3,
        "flip_x": False,
        "flip_y": True,
        "flip_diagonal": True,
    }
    code, absent = run(
        "tilemap", "get", sprite_file=str(source), target={**target, "frame_number": 2}
    )
    assert code == 0 and absent["tilemap"]["exists"] is False, absent


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_tile_images_use_existing_pixel_snapshot_modes(
    tmp_path: Path, runtime, mode: str
) -> None:
    source = tmp_path / "tiles.aseprite"
    fixture(source, runtime, mode=mode)
    code, result = run(
        "tileset",
        "tile",
        "get",
        sprite_file=str(source),
        target={"tileset_index": 1},
        tile={"tile_key": "green"},
    )
    assert code == 0, result
    assert result["snapshot"]["color_mode"] == mode
    assert result["tile"]["tile_index"] == 2


def test_large_region_artifact_is_same_schema_and_has_no_truncated_cells(
    tmp_path: Path, runtime
) -> None:
    import hashlib
    import json

    from spa.authoring.tile.values import TileRegionSnapshot

    source, destination = tmp_path / "large.aseprite", tmp_path / "region.json"
    fixture(source, runtime, map_width=65, map_height=65)
    original = source.read_bytes()
    target = {"layer": {"layer_name": "map"}, "frame_number": 1}
    rectangle = {"x": 0, "y": 0, "width": 65, "height": 65}
    code, refused = run(
        "tilemap", "get", sprite_file=str(source), target=target, rectangle=rectangle
    )
    assert code != 0 and refused["code"] == "tile_snapshot_destination_required", (
        refused
    )
    code, result = run(
        "tilemap",
        "get",
        sprite_file=str(source),
        target=target,
        rectangle=rectangle,
        snapshot_destination={"path": str(destination), "if_exists": "fail"},
    )
    assert (
        code == 0 and result["output_form"] == "artifact" and result["snapshot"] is None
    ), result
    raw = destination.read_bytes()
    snapshot = TileRegionSnapshot.model_validate_json(raw)
    assert snapshot.entries[-1].tile_x == 64 and snapshot.entries[-1].tile_y == 64
    assert len(snapshot.entries) == 5
    assert result["artifact"]["sha256"] == hashlib.sha256(raw).hexdigest()
    small = {"x": 0, "y": 0, "width": 3, "height": 2}
    code, inline = run(
        "tilemap", "get", sprite_file=str(source), target=target, rectangle=small
    )
    assert code == 0, inline
    code, exported = run(
        "tilemap",
        "get",
        sprite_file=str(source),
        target=target,
        rectangle=small,
        snapshot_destination={"path": str(destination), "if_exists": "replace"},
    )
    assert code == 0, exported
    assert json.loads(destination.read_bytes()) == inline["snapshot"]
    assert source.read_bytes() == original


def test_precise_addresses_missing_cels_and_region_bounds_fail_without_writes(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    fixture(source, runtime, duplicate_name="true")
    original = source.read_bytes()
    for target, failure in [
        ({"tileset_name": "terrain"}, "tileset_ambiguous"),
        ({"tileset_index": 2**53 + 1}, "tileset_missing"),
        ({"layer": {"layer_path": [1]}}, "tilemap_layer_required"),
        ({"layer": {"layer_name": "missing"}}, "layer_missing"),
    ]:
        code, result = run("tileset", "get", sprite_file=str(source), target=target)
        assert code != 0 and result["code"] == failure, result
    target = {"layer": {"layer_name": "map"}, "frame_number": 1}
    area = {"x": 0, "y": 0, "width": 1, "height": 1}
    for selected, rectangle, failure in [
        ({**target, "frame_number": 2}, area, "tilemap_cel_missing"),
        ({**target, "frame_number": 2**53 + 1}, area, "tilemap_frame_out_of_bounds"),
        (target, {**area, "x": 3}, "tile_region_out_of_bounds"),
        (target, {**area, "x": -1}, "tile_region_out_of_bounds"),
        (target, {**area, "width": 2**53 + 1}, "tile_region_out_of_bounds"),
    ]:
        code, result = run(
            "tilemap",
            "get",
            sprite_file=str(source),
            target=selected,
            rectangle=rectangle,
        )
        assert code != 0 and result["code"] == failure, result
    assert source.read_bytes() == original


def test_base_index_never_changes_tile_keys_or_placements(
    tmp_path: Path, runtime
) -> None:
    source, other = tmp_path / "original.aseprite", tmp_path / "other.aseprite"
    fixture(source, runtime, base_index=1)
    fixture(other, runtime, base_index=77)
    payload = {
        "target": {"layer": {"layer_name": "map"}, "frame_number": 1},
        "rectangle": {"x": 0, "y": 0, "width": 3, "height": 2},
    }
    code, before = run("tilemap", "get", sprite_file=str(source), **payload)
    assert code == 0, before
    code, after = run("tilemap", "get", sprite_file=str(other), **payload)
    assert code == 0, after
    assert before["snapshot"] == after["snapshot"]
    assert before["tileset"]["base_index"] == 1 and after["tileset"]["base_index"] == 77


def test_lists_existing_cells_and_validates_exact_frame_scope(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    fixture(source, runtime)
    code, result = run("tilemap", "list", sprite_file=str(source))
    assert code == 0 and result["frame_count"] == 2, result
    assert [
        (item["layer"]["name"], item["frame_number"]) for item in result["cels"]
    ] == [("map", 1), ("shared", 2)]
    assert all("entries" not in item for item in result["cels"])
    code, checked = run(
        "tilemap",
        "validate",
        sprite_file=str(source),
        target={"layer": {"layer_name": "shared"}, "frame_number": 2},
    )
    assert code == 0 and checked["valid"] is False, checked
    assert checked["tilemap"]["frame_number"] == 2


def test_invalid_native_reference_is_observed_and_reported_without_dropping_cell(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    fixture(source, runtime, invalid_index="true")
    target = {"layer": {"layer_name": "map"}, "frame_number": 1}
    code, result = run(
        "tilemap",
        "get",
        sprite_file=str(source),
        target=target,
        rectangle={"x": 1, "y": 0, "width": 2, "height": 1},
    )
    assert code == 0, result
    first = result["snapshot"]["entries"][0]
    assert (first["tile_x"], first["tile_y"]) == (1, 0)
    assert (
        first["placement"]["tile_index"] == 99
        and first["placement"]["tile_key"] is None
    )
    assert first["placement"]["flip_x"] is True
    code, checked = run("tilemap", "validate", sprite_file=str(source), target=target)
    assert code == 0, checked
    finding = next(
        item
        for item in checked["findings"]
        if item["code"] == "tile_index_out_of_bounds"
    )
    assert finding["tile_index"] == 99 and finding["frame_number"] == 1
    assert (finding["tile_x"], finding["tile_y"]) == (1, 0)
