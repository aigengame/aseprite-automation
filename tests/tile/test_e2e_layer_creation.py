"""Explicit Tilemap Layer creation through the installed Layer operation."""

from pathlib import Path

import pytest

from tests.support import clear_first_saved_layer_uuid
from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("plan", [False, True], ids=["standalone", "plan"])
@pytest.mark.parametrize("intent", ["create", "share"])
def test_new_tilemap_layer_accepts_explicit_cel_creation(
    tmp_path: Path, runtime, intent: str, plan: bool
) -> None:
    source = tmp_path / "source.aseprite"
    layered = tmp_path / "layered.aseprite"
    target = tmp_path / "target.aseprite"
    fixture(source, runtime, mode="indexed", transparent="7")
    original = source.read_bytes()
    tileset = (
        {
            "create": {
                "name": "new terrain",
                "grid": {
                    "origin": {"x": 0, "y": 0},
                    "tile_size": {"width": 2, "height": 3},
                },
                "base_index": 1,
            }
        }
        if intent == "create"
        else {"share": {"tileset_index": 1}}
    )
    code, added = run(
        "layer",
        "add",
        source_sprite_file=str(source),
        target_sprite_file=str(layered),
        in_place=False,
        overwrite=False,
        kind="tilemap",
        name="new map",
        tileset=tileset,
    )
    assert code == 0, added
    assert added["tilemap"]["initial_cel_count"] == 0
    layered_bytes = layered.read_bytes()
    address = {
        "layer": {"layer_path": added["layer"]["path"]},
        "frame_number": 1,
    }
    size = {"width": 2, "height": 3}
    files = {
        "source_sprite_file": str(layered),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
    }
    inputs = {"target": address, "tilemap_size": size}
    code, result = (
        run(
            "plan",
            "run",
            plan=files | {"steps": [{"operation": "cel add", "input": inputs}]},
        )
        if plan
        else run("cel", "add", **files, **inputs)
    )
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target=address,
        rectangle={"x": 0, "y": 0, **size},
    )
    assert code == 0, observed
    assert observed["tilemap"]["cell_size"] == size
    assert (
        observed["tilemap"]["tileset_index"]
        == added["tilemap"]["tileset"]["tileset_index"]
    )
    assert observed["snapshot"]["complete"] is True
    assert observed["snapshot"]["entries"] == []
    code, final_tilesets = run("tileset", "list", sprite_file=str(target))
    assert code == 0, final_tilesets
    assert len(final_tilesets["tilesets"]) == added["tilemap"]["tileset_count"]
    assert source.read_bytes() == original
    assert layered.read_bytes() == layered_bytes


@pytest.mark.parametrize(
    "mode,base_index", [("rgb", -32768), ("grayscale", -1), ("indexed", 32767)]
)
def test_create_tilemap_layer_preserves_existing_document(
    tmp_path: Path, runtime, mode: str, base_index: int
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, mode=mode, transparent="7")
    original = source.read_bytes()
    code, before = run("tileset", "list", sprite_file=str(source))
    assert code == 0, before
    grid = {"origin": {"x": 0, "y": 0}, "tile_size": {"width": 4, "height": 5}}
    code, added = run(
        "layer",
        "add",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        kind="tilemap",
        name="new map",
        tileset={
            "create": {"name": "new terrain", "grid": grid, "base_index": base_index}
        },
    )
    assert code == 0, added
    assert added["persisted_reopen_verified"] is True
    assert added["layer"]["is_tilemap"] is True
    assert added["layer"]["name"] == "new map"
    created = added["tilemap"]
    assert created["tileset"]["name"] == "new terrain"
    assert created["tileset"]["grid"] == grid
    assert created["tileset"]["base_index"] == base_index
    assert created["tileset"]["tile_count"] == 1
    assert created["initial_cel_count"] == 0
    assert created["tileset_count"] == len(before["tilesets"]) + 1
    assert created["temporary_tilesets_removed"] == 0
    code, after = run("tileset", "list", sprite_file=str(target))
    assert code == 0, after
    assert after["tilesets"][:-1] == before["tilesets"]
    assert after["tilesets"][-1] == created["tileset"]
    code, cell = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target={"layer": {"layer_path": added["layer"]["path"]}, "frame_number": 2},
    )
    assert code == 0, cell
    assert cell["tilemap"]["exists"] is False
    code, document = run(
        "sprite", "get", sprite_file=str(target), inspection_scope=["tilesets"]
    )
    assert code == 0, document
    assert document["tilesets"][-1]["base_index"] == base_index
    assert source.read_bytes() == original


@pytest.mark.parametrize("address", [{"tileset_index": 1}, {"tileset_name": "orphan"}])
def test_share_removes_only_its_temporary_tileset(
    tmp_path: Path, runtime, address: dict
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, properties="true")
    original = source.read_bytes()
    code, before = run("tileset", "list", sprite_file=str(source))
    assert code == 0, before
    code, added = run(
        "layer",
        "add",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        kind="tilemap",
        name="new shared map",
        tileset={"share": address},
    )
    assert code == 0, added
    result = added["tilemap"]
    selected = before["tilesets"][0 if "tileset_index" in address else -1]
    assert result["shared_tileset_before"] == selected
    assert result["tileset"]["tileset_index"] == selected["tileset_index"]
    assert result["tileset_count"] == len(before["tilesets"])
    assert result["temporary_tilesets_removed"] == 1
    assert result["initial_cel_count"] == 0
    code, after = run("tileset", "list", sprite_file=str(target))
    assert code == 0, after
    assert len(after["tilesets"]) == len(before["tilesets"])
    for current, previous in zip(after["tilesets"], before["tilesets"], strict=True):
        current["layers"] = [
            item for item in current["layers"] if item["name"] != "new shared map"
        ]
        assert current == previous
    for destination in (source, target):
        code, tile = run(
            "tileset",
            "tile",
            "get",
            sprite_file=str(destination),
            target={"tileset_index": 1},
            tile={"tile_index": 2},
            property_namespaces=["example.tiles", "not.requested"],
        )
        assert code == 0, tile
        observed = {key: tile[key] for key in ("tile", "snapshot")}
        if destination == source:
            expected = observed
        else:
            assert observed == expected
    assert source.read_bytes() == original


def test_share_accepts_native_assignment_of_an_unverified_layer_uuid(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, uuids="true")
    clear_first_saved_layer_uuid(source, "map")
    original = source.read_bytes()
    code, before = run("tileset", "list", sprite_file=str(source))
    assert code == 0, before
    existing_bindings = before["tilesets"][0]["layers"]
    assert [binding["name"] for binding in existing_bindings] == ["map", "shared"]
    assert existing_bindings[0]["layer_uuid"] is None
    assert isinstance(existing_bindings[1]["layer_uuid"], str)

    code, added = run(
        "layer",
        "add",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        kind="tilemap",
        name="added",
        tileset={"share": {"tileset_index": 1}},
    )
    assert code == 0, added
    assert added["persisted_reopen_verified"] is True
    assert added["use_layer_uuids"] is True
    assert added["tilemap"]["shared_tileset_before"] == before["tilesets"][0]
    assert added["tilemap"]["tileset_count"] == len(before["tilesets"])
    assert added["tilemap"]["temporary_tilesets_removed"] == 1

    code, after = run("tileset", "list", sprite_file=str(target))
    assert code == 0, after
    assert after["tilesets"][0] == added["tilemap"]["tileset"]
    retained = after["tilesets"][0]["layers"][:-1]
    assigned_uuid = retained[0]["layer_uuid"]
    assert isinstance(assigned_uuid, str) and assigned_uuid
    assert retained == [
        existing_bindings[0] | {"layer_uuid": assigned_uuid},
        existing_bindings[1],
    ]
    assert after["tilesets"][1:] == before["tilesets"][1:]
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "parent_kind,persist",
    [("layer_path", False), ("layer_name", True), ("layer_uuid", True)],
)
def test_tilemap_appends_to_exact_group_and_preserves_uuid_policy(
    tmp_path: Path, runtime, parent_kind: str, persist: bool
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, group="true", uuids=str(persist).lower())
    code, before = run("layer", "list", sprite_file=str(source))
    assert code == 0, before
    parent = before["layers"][-1]
    address = {
        "layer_path": parent["path"],
        "layer_name": parent["name"],
        "layer_uuid": parent["layer_uuid"],
    }
    code, added = run(
        "layer",
        "add",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        kind="tilemap",
        name="nested map",
        parent={parent_kind: address[parent_kind]},
        tileset={"share": {"tileset_index": 1}},
    )
    assert code == 0, added
    assert added["layer"]["path"] == [*parent["path"], 2]
    assert added["use_layer_uuids"] is persist
    assert (added["layer"]["layer_uuid"] is not None) is persist
    code, after = run("layer", "list", sprite_file=str(target))
    assert code == 0, after
    assert after["layers"][-1]["children"].pop() == added["layer"]
    assert after == {**before, "sprite_file": str(target)}


@pytest.mark.parametrize(
    "address,expected",
    [
        ({"tileset_index": 999}, "tileset_missing"),
        ({"tileset_index": 2**53 + 1}, "tileset_missing"),
        ({"tileset_name": "absent"}, "tileset_missing"),
        ({"tileset_name": "terrain"}, "tileset_ambiguous"),
    ],
)
def test_invalid_share_preserves_source_and_existing_target(
    tmp_path: Path, runtime, address: dict, expected: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, duplicate_name="true")
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    code, failure = run(
        "layer",
        "add",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        kind="tilemap",
        name="new map",
        tileset={"share": address},
    )
    assert code == 2, failure
    assert failure["code"] == expected
    assert {
        key: value
        for key, value in failure["details"]["target"].items()
        if value is not None
    } == address
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"
    assert set(tmp_path.iterdir()) == {source, target}


def test_tilemap_parent_refusal_preserves_in_place_source(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "source.aseprite"
    fixture(source, runtime)
    original = source.read_bytes()
    code, failure = run(
        "layer",
        "add",
        source_sprite_file=str(source),
        target_sprite_file=str(source),
        in_place=True,
        overwrite=True,
        kind="tilemap",
        name="new map",
        parent={"layer_path": [1]},
        tileset={"share": {"tileset_index": 1}},
    )
    assert code == 2, failure
    assert failure["code"] == "layer_parent_not_group"
    assert source.read_bytes() == original
    assert set(tmp_path.iterdir()) == {source}
