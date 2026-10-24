"""Public Tile inspection preserves existing native content and identities."""

from pathlib import Path

import pytest

from tests.native_invocation import expect_success, run
from tests.tile.support import tiles_sprite

pytestmark = pytest.mark.e2e


def test_properties_are_lua_observations_in_declared_namespaces(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "properties.aseprite"
    tiles_sprite(runtime, source, properties="true")
    original = source.read_bytes()
    request = {
        "sprite_file": str(source),
        "target": {"tileset_index": 1},
        "tile": {"tile_key": "green"},
    }
    default = expect_success("tileset tile get", request)
    assert [item["namespace"] for item in default["tile"]["properties"]] == [
        "",
        "aigengame.spa",
    ]
    observed = expect_success(
        "tileset tile get",
        {
            **request,
            "property_namespaces": [
                "example.tiles",
                "aigengame.spa",
                "example.tiles",
                "absent",
            ],
        },
    )
    properties = {
        item["namespace"]: {
            entry["key"]["value"]: entry["value"] for entry in item["value"]["entries"]
        }
        for item in observed["tile"]["properties"]
    }
    assert list(properties) == ["", "aigengame.spa", "example.tiles", "absent"]
    assert properties["example.tiles"] == {
        "walkable": {"kind": "boolean", "value": True}
    }
    assert properties["aigengame.spa"] == {
        "tile_key": {"kind": "string", "value": "green"}
    }
    assert properties["absent"] == {}
    assert properties[""] == {
        "title": {"kind": "string", "value": "stone"},
        "visible": {"kind": "boolean", "value": True},
        "integer": {"kind": "integer", "value": "9007199254740993"},
        "ratio": {"kind": "number", "value": 1.25},
        "anchor": {"kind": "point", "x": 2, "y": -3},
        "extent": {"kind": "size", "width": 4, "height": 5},
        "bounds": {"kind": "rectangle", "x": 1, "y": 2, "width": 3, "height": 4},
        "uuid": {"kind": "uuid", "value": "01234567-89ab-cdef-0123-456789abcdef"},
        "nested": {
            "kind": "table",
            "entries": [
                {
                    "key": {"kind": "string", "value": "label"},
                    "value": {"kind": "string", "value": "nested"},
                },
                {
                    "key": {"kind": "string", "value": "offset"},
                    "value": {"kind": "point", "x": 4, "y": 6},
                },
            ],
        },
        "sequence": {
            "kind": "table",
            "entries": [
                {
                    "key": {"kind": "integer", "value": "1"},
                    "value": {"kind": "string", "value": "first"},
                },
                {
                    "key": {"kind": "integer", "value": "2"},
                    "value": {"kind": "string", "value": "second"},
                },
            ],
        },
        "empty": {"kind": "table", "entries": []},
        "infinity": {"kind": "unavailable", "reason": "non_finite_number"},
    }
    all_tiles = expect_success(
        "tileset get",
        {
            "sprite_file": str(source),
            "target": {"tileset_index": 1},
            "property_namespaces": ["example.tiles", "absent"],
        },
    )
    assert all_tiles["tiles"][2]["properties"] == observed["tile"]["properties"]
    # Native Tile 0's Lua Properties getter exposes Tileset user data.
    assert all_tiles["tiles"][0]["tile_key"] is None
    assert all_tiles["tiles"][0]["properties"][1]["value"]["entries"] == [
        {
            "key": {"kind": "string", "value": "tile_key"},
            "value": {"kind": "string", "value": "tileset metadata"},
        }
    ]
    checked = expect_success(
        "tileset validate", {"sprite_file": str(source), "target": {"tileset_index": 1}}
    )
    assert {item["code"] for item in checked["findings"]} == {
        "tile_key_missing",
        "tile_key_duplicate",
    }
    assert source.read_bytes() == original


def test_lists_multiple_tilesets_and_shared_layer_bindings_without_repair(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    tiles_sprite(runtime, source)
    original = source.read_bytes()
    result = expect_success("tileset list", {"sprite_file": str(source)})
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
    tiles_sprite(runtime, source, base_index=10)
    original = source.read_bytes()
    result = expect_success(
        "tileset get",
        {"sprite_file": str(source), "target": {"tileset_name": "terrain"}},
    )
    assert [tile["tile_key"] for tile in result["tiles"]] == [
        None,
        "red",
        "green",
        None,
        "red",
    ]
    assert [tile["display_index"] for tile in result["tiles"]] == [9, 10, 11, 12, 13]
    tile = expect_success(
        "tileset tile get",
        {
            "sprite_file": str(source),
            "target": {"layer": {"layer_name": "map"}},
            "tile": {"tile_index": 3},
        },
    )
    assert tile["tile"]["tile_key"] is None
    assert tile["snapshot"]["rectangle"] == {"x": 0, "y": 0, "width": 2, "height": 3}
    assert tile["snapshot"]["rows"][0][0]["color"]["red"] == 120
    for address, failure in [
        ({"tile_key": "red"}, "tile_key_ambiguous"),
        ({"tile_key": "unknown"}, "tile_key_missing"),
        ({"tile_index": 100}, "tile_index_out_of_bounds"),
    ]:
        outcome = run(
            "tileset tile get",
            {
                "sprite_file": str(source),
                "target": {"tileset_index": 1},
                "tile": address,
            },
        )
        rejected = outcome.envelope
        assert outcome.returncode != 0 and rejected["code"] == failure, rejected
    checked = expect_success(
        "tileset validate", {"sprite_file": str(source), "target": {"tileset_index": 1}}
    )
    assert checked["valid"] is False, checked
    assert {finding["code"] for finding in checked["findings"]} == {
        "tile_key_missing",
        "tile_key_duplicate",
    }
    assert source.read_bytes() == original


def test_tilemap_region_is_complete_sparse_and_uses_cel_local_coordinates(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    tiles_sprite(runtime, source)
    target = {"layer": {"layer_name": "map"}, "frame_number": 1}
    topology = expect_success(
        "tilemap get", {"sprite_file": str(source), "target": target}
    )
    assert topology["snapshot"] is None
    assert topology["tilemap"]["canvas_coverage"] == {
        "x": -5,
        "y": 7,
        "width": 6,
        "height": 6,
    }
    assert topology["tilemap"]["effective_grid"]["origin"] == {"x": -5, "y": 7}
    rectangle = {"x": 0, "y": 0, "width": 3, "height": 2}
    result = expect_success(
        "tilemap get",
        {"sprite_file": str(source), "target": target, "rectangle": rectangle},
    )
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
    absent = expect_success(
        "tilemap get",
        {"sprite_file": str(source), "target": {**target, "frame_number": 2}},
    )
    assert absent["tilemap"]["exists"] is False, absent


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_tile_images_use_existing_pixel_snapshot_modes(
    tmp_path: Path, runtime, mode: str
) -> None:
    import hashlib
    import json

    source = tmp_path / "tiles.aseprite"
    tiles_sprite(runtime, source, mode=mode)
    original = source.read_bytes()
    result = expect_success(
        "tileset tile get",
        {
            "sprite_file": str(source),
            "target": {"tileset_index": 1},
            "tile": {"tile_key": "green"},
        },
    )
    assert result["snapshot"]["color_mode"] == mode
    assert result["tile"]["tile_index"] == 2
    destination = tmp_path / "tile.json"
    artifact = expect_success(
        "tileset tile get",
        {
            "sprite_file": str(source),
            "target": {"tileset_index": 1},
            "tile": {"tile_key": "green"},
            "snapshot_destination": {"path": str(destination), "if_exists": "fail"},
        },
    )
    raw = destination.read_bytes()
    assert json.loads(raw) == result["snapshot"]
    assert artifact["snapshot"] is None and artifact["output_form"] == "artifact"
    assert artifact["artifact"] == {
        "role": "pixel-region-snapshot",
        "media_type": "application/json",
        "format": "json",
        "path": str(destination),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".*.staged.json"))


def test_large_region_artifact_is_same_schema_and_has_no_truncated_cells(
    tmp_path: Path, runtime
) -> None:
    import hashlib
    import json

    from spa.authoring.tile.values import TileRegionSnapshot

    source, destination = tmp_path / "large.aseprite", tmp_path / "region.json"
    tiles_sprite(runtime, source, map_width=65, map_height=65)
    original = source.read_bytes()
    target = {"layer": {"layer_name": "map"}, "frame_number": 1}
    rectangle = {"x": 0, "y": 0, "width": 65, "height": 65}
    outcome = run(
        "tilemap get",
        {"sprite_file": str(source), "target": target, "rectangle": rectangle},
    )
    refused = outcome.envelope
    assert (
        outcome.returncode != 0
        and refused["code"] == "tile_snapshot_destination_required"
    ), refused
    assert refused["details"]["snapshot_limit"] == {
        "unit": "tile_cells",
        "maximum_inline": 4096,
        "requested": 4225,
    }
    result = expect_success(
        "tilemap get",
        {
            "sprite_file": str(source),
            "target": target,
            "rectangle": rectangle,
            "snapshot_destination": {"path": str(destination), "if_exists": "fail"},
        },
    )
    assert result["output_form"] == "artifact" and result["snapshot"] is None, result
    raw = destination.read_bytes()
    snapshot = TileRegionSnapshot.model_validate_json(raw)
    assert snapshot.entries[-1].tile_x == 64 and snapshot.entries[-1].tile_y == 64
    assert len(snapshot.entries) == 5
    assert result["artifact"] == {
        "role": "tile-region-snapshot",
        "media_type": "application/json",
        "format": "json",
        "path": str(destination),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    small = {"x": 0, "y": 0, "width": 3, "height": 2}
    inline = expect_success(
        "tilemap get",
        {"sprite_file": str(source), "target": target, "rectangle": small},
    )
    expect_success(
        "tilemap get",
        {
            "sprite_file": str(source),
            "target": target,
            "rectangle": small,
            "snapshot_destination": {"path": str(destination), "if_exists": "replace"},
        },
    )
    assert json.loads(destination.read_bytes()) == inline["snapshot"]
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".*.staged.json"))


def test_large_tile_image_failure_reports_its_inline_pixel_limit(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "large-tile.aseprite"
    tiles_sprite(runtime, source, tile_width=65, tile_height=65)
    original = source.read_bytes()
    outcome = run(
        "tileset tile get",
        {
            "sprite_file": str(source),
            "target": {"tileset_index": 1},
            "tile": {"tile_key": "green"},
        },
    )
    refused = outcome.envelope
    assert (
        outcome.returncode != 0
        and refused["code"] == "tile_snapshot_destination_required"
    ), refused
    assert refused["details"]["snapshot_limit"] == {
        "unit": "pixels",
        "maximum_inline": 4096,
        "requested": 4225,
    }
    assert source.read_bytes() == original


@pytest.mark.parametrize("position", ["value", "nested-key", "root-key"])
def test_unrepresentable_lua_text_is_explicit_without_losing_other_namespaces(
    tmp_path: Path, runtime, position: str
) -> None:
    source = tmp_path / "bytes.aseprite"
    tiles_sprite(runtime, source, byte_property=position)
    original = source.read_bytes()
    request = {"sprite_file": str(source), "target": {"tileset_index": 1}}
    result = expect_success(
        "tileset tile get", {**request, "tile": {"tile_key": "green"}}
    )
    namespaces = {
        item["namespace"]: item["value"] for item in result["tile"]["properties"]
    }
    value = namespaces[""]
    if position != "root-key":
        entry = next(
            item for item in value["entries"] if item["key"]["value"] == "binary"
        )
        value = entry["value"]
    assert value == {"kind": "unavailable", "reason": "non_utf8_string"}
    assert namespaces["aigengame.spa"] == {
        "kind": "table",
        "entries": [
            {
                "key": {"kind": "string", "value": "tile_key"},
                "value": {"kind": "string", "value": "green"},
            }
        ],
    }
    all_tiles = expect_success("tileset get", request)
    assert all_tiles["tiles"][2]["properties"] == result["tile"]["properties"]
    assert source.read_bytes() == original


def test_unrepresentable_tile_key_keeps_index_reads_and_validation_available(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "byte-key.aseprite"
    tiles_sprite(runtime, source, byte_property="tile-key")
    original = source.read_bytes()
    request = {"sprite_file": str(source), "target": {"tileset_index": 1}}
    result = expect_success("tileset tile get", {**request, "tile": {"tile_index": 2}})
    assert result["tile"]["tile_key"] is None
    assert result["tile"]["properties"][1]["value"]["entries"] == [
        {
            "key": {"kind": "string", "value": "tile_key"},
            "value": {"kind": "unavailable", "reason": "non_utf8_string"},
        }
    ]
    tiles = expect_success("tileset get", request)
    assert tiles["tiles"][2] == result["tile"]
    tilemap = {
        "sprite_file": str(source),
        "target": {"layer": {"layer_name": "map"}, "frame_number": 1},
    }
    region = expect_success(
        "tilemap get",
        {**tilemap, "rectangle": {"x": 2, "y": 0, "width": 1, "height": 1}},
    )
    assert region["snapshot"]["entries"][0]["placement"] == {
        "kind": "tile",
        "tile_index": 2,
        "tile_key": None,
        "flip_x": True,
        "flip_y": False,
        "flip_diagonal": False,
    }
    for operation, query in [("tileset", request), ("tilemap", tilemap)]:
        checked = expect_success(f"{operation} validate", query)
        assert checked["valid"] is False, checked
        finding = next(item for item in checked["findings"] if item["tile_index"] == 2)
        assert finding["code"] == "tile_key_invalid"
        assert finding["tile_key"] is None
    assert source.read_bytes() == original


def test_precise_addresses_missing_cels_and_region_bounds_fail_without_writes(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    tiles_sprite(runtime, source, duplicate_name="true")
    original = source.read_bytes()
    for target, failure in [
        ({"tileset_name": "terrain"}, "tileset_ambiguous"),
        ({"tileset_index": 2**53 + 1}, "tileset_missing"),
        ({"layer": {"layer_path": [1]}}, "tilemap_layer_required"),
        ({"layer": {"layer_name": "missing"}}, "layer_missing"),
    ]:
        outcome = run("tileset get", {"sprite_file": str(source), "target": target})
        result = outcome.envelope
        assert outcome.returncode != 0 and result["code"] == failure, result
    target = {"layer": {"layer_name": "map"}, "frame_number": 1}
    area = {"x": 0, "y": 0, "width": 1, "height": 1}
    for selected, rectangle, failure in [
        ({**target, "frame_number": 2}, area, "tilemap_cel_missing"),
        ({**target, "frame_number": 2**53 + 1}, area, "tilemap_frame_out_of_bounds"),
        (target, {**area, "x": 3}, "tile_region_out_of_bounds"),
        (target, {**area, "x": -1}, "tile_region_out_of_bounds"),
        (target, {**area, "width": 2**53 + 1}, "tile_region_out_of_bounds"),
    ]:
        outcome = run(
            "tilemap get",
            {"sprite_file": str(source), "target": selected, "rectangle": rectangle},
        )
        result = outcome.envelope
        assert outcome.returncode != 0 and result["code"] == failure, result
    assert source.read_bytes() == original


def test_base_index_never_changes_tile_keys_or_placements(
    tmp_path: Path, runtime
) -> None:
    source, other = tmp_path / "original.aseprite", tmp_path / "other.aseprite"
    tiles_sprite(runtime, source, base_index=1)
    tiles_sprite(runtime, other, base_index=77)
    payload = {
        "target": {"layer": {"layer_name": "map"}, "frame_number": 1},
        "rectangle": {"x": 0, "y": 0, "width": 3, "height": 2},
    }
    before = expect_success("tilemap get", {"sprite_file": str(source), **payload})
    after = expect_success("tilemap get", {"sprite_file": str(other), **payload})
    assert before["snapshot"] == after["snapshot"]
    assert before["tileset"]["base_index"] == 1 and after["tileset"]["base_index"] == 77


def test_lists_existing_cells_and_validates_exact_frame_scope(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    tiles_sprite(runtime, source)
    result = expect_success("tilemap list", {"sprite_file": str(source)})
    assert result["frame_count"] == 2, result
    assert [
        (item["layer"]["name"], item["frame_number"]) for item in result["cels"]
    ] == [("map", 1), ("shared", 2)]
    assert all("entries" not in item for item in result["cels"])
    checked = expect_success(
        "tilemap validate",
        {
            "sprite_file": str(source),
            "target": {"layer": {"layer_name": "shared"}, "frame_number": 2},
        },
    )
    assert checked["valid"] is False, checked
    assert checked["tilemap"]["frame_number"] == 2


def test_invalid_native_reference_is_observed_and_reported_without_dropping_cell(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "tiles.aseprite"
    tiles_sprite(runtime, source, invalid_index="true")
    target = {"layer": {"layer_name": "map"}, "frame_number": 1}
    result = expect_success(
        "tilemap get",
        {
            "sprite_file": str(source),
            "target": target,
            "rectangle": {"x": 1, "y": 0, "width": 2, "height": 1},
        },
    )
    first = result["snapshot"]["entries"][0]
    assert (first["tile_x"], first["tile_y"]) == (1, 0)
    assert (
        first["placement"]["tile_index"] == 99
        and first["placement"]["tile_key"] is None
    )
    assert first["placement"]["flip_x"] is True
    checked = expect_success(
        "tilemap validate", {"sprite_file": str(source), "target": target}
    )
    finding = next(
        item
        for item in checked["findings"]
        if item["code"] == "tile_index_out_of_bounds"
    )
    assert finding["tile_index"] == 99 and finding["frame_number"] == 1
    assert (finding["tile_x"], finding["tile_y"]) == (1, 0)


def test_flagged_index_zero_is_observed_and_reported_without_repair(
    tmp_path: Path, runtime
) -> None:
    import json

    source, destination = tmp_path / "tiles.aseprite", tmp_path / "region.json"
    tiles_sprite(runtime, source, flagged_zero="true")
    original = source.read_bytes()
    target = {"layer": {"layer_name": "map"}, "frame_number": 1}
    request = {
        "sprite_file": str(source),
        "target": target,
        "rectangle": {"x": 1, "y": 0, "width": 1, "height": 2},
    }
    result = expect_success("tilemap get", request)
    assert result["snapshot"]["entries"] == [
        {
            "tile_x": 1,
            "tile_y": 0,
            "placement": {
                "kind": "tile",
                "tile_index": 0,
                "tile_key": None,
                "flip_x": True,
                "flip_y": True,
                "flip_diagonal": True,
            },
        }
    ]
    expect_success(
        "tilemap get",
        {
            **request,
            "snapshot_destination": {"path": str(destination), "if_exists": "fail"},
        },
    )
    assert json.loads(destination.read_bytes()) == result["snapshot"]
    for command, selected, expected_frames in [
        ("tilemap", target, [1]),
        ("tileset", {"tileset_index": 1}, [1, 2]),
    ]:
        checked = expect_success(
            f"{command} validate", {"sprite_file": str(source), "target": selected}
        )
        assert checked["valid"] is False, checked
        findings = [
            item for item in checked["findings"] if item["code"] == "empty_tile_flags"
        ]
        assert [item["frame_number"] for item in findings] == expected_frames
        assert all(
            (item["tile_index"], item["tile_x"], item["tile_y"]) == (0, 1, 0)
            for item in findings
        )
    assert source.read_bytes() == original
