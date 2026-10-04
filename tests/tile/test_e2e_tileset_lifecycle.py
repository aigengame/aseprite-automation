"""Tileset lifecycle through the public CLI and persisted native documents."""

from pathlib import Path

import pytest

from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


def files(source: Path, target: Path) -> dict:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": source == target,
        "overwrite": source == target,
    }


def test_remove_orphan_keeps_referenced_tileset(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "removed.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    original = source.read_bytes()
    code, result = run(
        "tileset", "remove", **files(source, target), target={"tileset_name": "orphan"}
    )
    assert code == 0, result
    assert result["removed_tileset"]["name"] == "orphan"
    assert result["removed_tileset"]["layers"] == []
    assert [item["name"] for item in result["tilesets"]] == ["terrain"]
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original
    code, observed = run("tileset", "list", sprite_file=str(target))
    assert code == 0, observed
    assert len(observed["tilesets"]) == 1


def test_remove_referenced_reports_every_layer_and_keeps_target(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    target.write_bytes(b"previous target")
    original = source.read_bytes()
    code, result = run(
        "tileset",
        "remove",
        **{**files(source, target), "overwrite": True},
        target={"tileset_name": "terrain"},
    )
    assert code != 0, result
    assert result["code"] == "tileset_in_use"
    assert {item["name"] for item in result["details"]["layers"]} == {"map", "peer"}
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"


def rebind(source: Path, target: Path, **extra: object) -> dict:
    return {
        **files(source, target),
        "layer": {"layer_name": "map"},
        "target": {"tileset_name": "destination"},
        "mapping": {"kind": "by_key"},
        "grid_policy": "require_equal",
        **extra,
    }


@pytest.mark.parametrize("explicit", [False, True])
def test_rebind_preserves_flags_links_metadata_and_other_layer(
    tmp_path: Path, runtime, explicit: bool
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "rebound.aseprite"
    fixture(source, runtime, script="tileset_lifecycle.lua", unkeyed=3)
    original = source.read_bytes()
    mapping = (
        {"kind": "by_key"}
        if not explicit
        else {
            "kind": "explicit",
            "entries": [
                {"source_key": "a", "target": {"kind": "tile", "tile_key": "a"}},
                {"source_key": "b", "target": {"kind": "empty"}},
            ],
        }
    )
    code, result = run(
        "layer", "set-tileset", **rebind(source, target, mapping=mapping)
    )
    assert code == 0, result
    assert result["tileset"]["name"] == "destination"
    assert len(result["cels"]) == 2
    assert [item["target_index"] for item in result["tile_mapping"]] == [
        2,
        0 if explicit else 1,
    ]
    fixture(
        target,
        runtime,
        script="verify_tileset_lifecycle.lua",
        explicit=str(explicit).lower(),
    )
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "parameters,code",
    [
        ({"unkeyed": 1}, "tile_key_missing"),
        ({"duplicate": "true"}, "tile_key_ambiguous"),
        ({"target_duplicate": "true"}, "tile_key_ambiguous"),
        ({"target_missing": "true"}, "tile_key_missing"),
        ({"flagged_empty": "true"}, "tile_key_missing"),
        ({"invalid_key": "true"}, "tile_key_missing"),
    ],
)
def test_rebind_refuses_unresolved_used_keys(
    tmp_path: Path, runtime, parameters: dict, code: str
) -> None:
    source = tmp_path / "source.aseprite"
    fixture(source, runtime, script="tileset_lifecycle.lua", **parameters)
    original = source.read_bytes()
    status, result = run("layer", "set-tileset", **rebind(source, source))
    assert status != 0, result
    assert result["code"] == code
    assert source.read_bytes() == original


def test_rebind_grid_policy_keeps_cells_and_positions(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "rebound.aseprite"
    fixture(source, runtime, script="tileset_lifecycle.lua", width=5, height=4)
    code, refused = run("layer", "set-tileset", **rebind(source, target))
    assert code != 0 and refused["details"]["reason"] == "grid_mismatch", refused
    assert not target.exists()
    code, result = run(
        "layer", "set-tileset", **rebind(source, target, grid_policy="use_target")
    )
    assert code == 0, result
    for cel in result["cels"]:
        assert cel["position"] == {"x": -3, "y": 7}
        assert cel["cell_size"] == {"width": 3, "height": 1}
        assert cel["before_coverage"] == {"x": -3, "y": 7, "width": 6, "height": 3}
        assert cel["canvas_coverage"] == {"x": -3, "y": 7, "width": 15, "height": 4}
    fixture(target, runtime, script="verify_tileset_lifecycle.lua")


@pytest.mark.parametrize("transparent,high_index", [(0, 7), (7, 2)])
def test_rebind_rejects_invalid_index_or_transparency_in_linked_usage_frame(
    tmp_path: Path, runtime, transparent: int, high_index: int
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(
        source,
        runtime,
        script="tileset_lifecycle.lua",
        mode="indexed",
        transparent=transparent,
        high_index=high_index,
    )
    inject_palette_change(source, [(i, 20, 30, 255) for i in range(4)], frame_number=2)
    target.write_bytes(b"previous target")
    original = source.read_bytes()
    code, result = run("layer", "set-tileset", **rebind(source, target, overwrite=True))
    assert code != 0, result
    assert result["code"] == "tileset_lifecycle_invalid"
    assert result["details"]["reason"] == "palette_index"
    assert result["details"]["frame_number"] == 2
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"


def test_indexed_rebind_checks_only_tiles_used_in_each_frame(
    tmp_path: Path, runtime
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(
        source,
        runtime,
        script="tileset_lifecycle.lua",
        mode="indexed",
        separate_frames="true",
    )
    inject_palette_change(
        source, [(i, 20, 30, 0 if i == 0 else 255) for i in range(4)], frame_number=1
    )
    inject_palette_change(
        source, [(i, 40, 50, 0 if i == 0 else 255) for i in range(8)], frame_number=2
    )
    code, result = run("layer", "set-tileset", **rebind(source, target))
    assert code == 0, result
    assert [
        (check["frame_number"], check["tile_indexes"])
        for check in result["palette_checks"]
    ] == [(1, [2]), (2, [1])]
    assert [
        check["effective_palette"]["palette_size"] for check in result["palette_checks"]
    ] == [4, 8]


def test_indexed_linked_rebind_allows_different_valid_frame_palettes(
    tmp_path: Path, runtime
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="tileset_lifecycle.lua", mode="indexed")
    inject_palette_change(
        source, [(i, 40, 50, 0 if i == 0 else 255) for i in range(8)], frame_number=2
    )
    code, result = run("layer", "set-tileset", **rebind(source, target))
    assert code == 0, result
    assert [check["frame_number"] for check in result["palette_checks"]] == [1, 2]
    assert [check["tile_indexes"] for check in result["palette_checks"]] == [
        [1, 2],
        [1, 2],
    ]
    fixture(target, runtime, script="verify_tileset_lifecycle.lua")


@pytest.mark.parametrize("keys", [["a"], ["a", "b", "unused"]])
def test_explicit_mapping_requires_exactly_used_keys(
    tmp_path: Path, runtime, keys: list[str]
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="tileset_lifecycle.lua")
    original = source.read_bytes()
    mapping = {
        "kind": "explicit",
        "entries": [{"source_key": key, "target": {"kind": "empty"}} for key in keys],
    }
    code, result = run(
        "layer", "set-tileset", **rebind(source, target, mapping=mapping)
    )
    assert code != 0, result
    assert result["code"] == "tileset_lifecycle_invalid"
    assert result["details"]["reason"] in {"mapping_incomplete", "mapping_invalid"}
    assert source.read_bytes() == original
    assert not target.exists()
