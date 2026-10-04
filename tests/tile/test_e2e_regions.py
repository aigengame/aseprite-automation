"""Tilemap region writes through the public CLI and persisted native Images."""

import json
from pathlib import Path

import pytest

from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


def placement(key: str = "c", **flags: bool) -> dict:
    return {
        "kind": "tile",
        "tile_key": key,
        "flip_x": False,
        "flip_y": False,
        "flip_diagonal": False,
        **flags,
    }


def files(source: Path, target: Path, frame: int = 1, **extra: object) -> dict:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_name": "map"}, "frame_number": frame},
        **extra,
    }


def test_set_replaces_sparse_region_and_preserves_linked_cels(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    before = source.read_bytes()
    code, result = run(
        "tilemap",
        "set",
        **files(source, target),
        snapshot={
            "coordinate_space": "tile-cell",
            "rectangle": {"x": 1, "y": 0, "width": 3, "height": 1},
            "complete": True,
            "default": {"kind": "empty"},
            "entries": [
                {"tile_x": 2, "tile_y": 0, "placement": placement("b", flip_y=True)}
            ],
        },
    )
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    assert result["cells_written"] == 3
    assert result["cells_changed"] == 3
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1, 2]
    assert source.read_bytes() == before
    for frame in (1, 2):
        code, observed = run(
            "tilemap",
            "get",
            sprite_file=str(target),
            target={"layer": {"layer_name": "map"}, "frame_number": frame},
            rectangle={"x": 0, "y": 0, "width": 5, "height": 1},
        )
        assert code == 0, observed
        assert observed["tilemap"]["position"] == {"x": -3, "y": 7}
        entries = observed["snapshot"]["entries"]
        assert [entry["tile_x"] for entry in entries] == [0, 2, 4]
        assert entries[1]["placement"] == placement("b", flip_y=True) | {
            "tile_index": 2
        }
        assert entries[-1]["placement"]["tile_index"] == 0
        assert entries[-1]["placement"]["tile_key"] is None
        assert result["affected_cels"][frame - 1]["linked_cels"] == [
            {"layer_path": [2], "frame_number": 3 - frame}
        ]


def test_patch_changes_only_explicit_cells(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    code, result = run(
        "tilemap",
        "patch",
        **files(source, target, frame=2),
        patch={
            "coordinate_space": "tile-cell",
            "entries": [
                {"tile_x": 4, "tile_y": 0, "placement": placement("a", flip_x=True)},
                {"tile_x": 2, "tile_y": 0, "placement": {"kind": "empty"}},
            ],
        },
    )
    assert code == 0, result
    assert result["cells_written"] == result["cells_changed"] == 2
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target={"layer": {"layer_name": "map"}, "frame_number": 1},
        rectangle={"x": 0, "y": 0, "width": 5, "height": 1},
    )
    assert code == 0, observed
    entries = observed["snapshot"]["entries"]
    assert [entry["tile_x"] for entry in entries] == [0, 1, 3, 4]
    assert entries[-1]["placement"] == placement("a", flip_x=True) | {"tile_index": 1}
    assert entries[1]["placement"] == placement(
        "b", flip_x=True, flip_y=True, flip_diagonal=True
    ) | {"tile_index": 2}


@pytest.mark.parametrize("mode", ["rgb", "grayscale"])
@pytest.mark.parametrize(
    "flags",
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
    ],
)
def test_fill_one_placement_and_empty_whole_image(
    tmp_path: Path, runtime, mode: str, flags: tuple
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode=mode)
    value = placement("d", flip_x=flags[0], flip_y=flags[1], flip_diagonal=flags[2])
    rectangle = {"x": 0, "y": 0, "width": 5, "height": 1}
    code, result = run(
        "tilemap",
        "fill",
        **files(source, target),
        coordinate_space="tile-cell",
        rectangle=rectangle,
        placement=value,
    )
    assert code == 0, result
    assert result["cells_written"] == 5
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target=files(source, target)["target"],
        rectangle=rectangle,
    )
    assert code == 0, observed
    assert [entry["placement"] for entry in observed["snapshot"]["entries"]] == [
        value | {"tile_index": 4}
    ] * 5
    code, result = run(
        "tilemap",
        "fill",
        **files(target, target, in_place=True, overwrite=True),
        coordinate_space="tile-cell",
        rectangle=rectangle,
        placement={"kind": "empty"},
    )
    assert code == 0, result
    assert result["cells_changed"] == 5
    assert result["tilemap"]["cell_size"] == {"width": 5, "height": 1}
    assert result["tilemap"]["position"] == {"x": -3, "y": 7}
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target=files(source, target)["target"],
        rectangle=rectangle,
    )
    assert code == 0 and observed["snapshot"]["entries"] == [], observed


def test_indexed_write_validates_linked_frame_not_tile_creation_basis(
    tmp_path: Path, runtime
) -> None:
    from tests.support import inject_palette_change
    from tests.tile.support import snapshot

    source, keyed, target = (
        tmp_path / name
        for name in ("source.aseprite", "keyed.aseprite", "target.aseprite")
    )
    fixture(source, runtime, script="lifecycle.lua", mode="indexed", palette_size=10)
    image = snapshot("indexed")
    for row in image["rows"]:
        row[0]["color"]["index"] = 9
    code, added = run(
        "tileset",
        "tile",
        "add",
        source_sprite_file=str(source),
        target_sprite_file=str(keyed),
        in_place=False,
        overwrite=False,
        target={"tileset_index": 1},
        tile_key="new",
        image=image,
        palette_frame_number=1,
    )
    assert code == 0, json.dumps(added, indent=2)
    assert added["effective_palette"]["frame_number"] == 1
    inject_palette_change(
        keyed, [(20 + i, 40, 60, 255) for i in range(8)], frame_number=2
    )
    before = keyed.read_bytes()
    target.write_bytes(b"prior Target")
    code, refused = run(
        "tilemap",
        "fill",
        **files(keyed, target, overwrite=True),
        coordinate_space="tile-cell",
        rectangle={"x": 0, "y": 0, "width": 1, "height": 1},
        placement=placement("new"),
    )
    assert code == 2, refused
    assert refused["code"] == "tilemap_region_invalid"
    assert refused["details"]["reason"] == "palette_incompatible"
    assert refused["details"]["frame_number"] == 2
    assert refused["details"]["palette_frame_number"] == 2
    assert refused["details"]["undefined_indexes"] == [9]
    assert keyed.read_bytes() == before
    assert target.read_bytes() == b"prior Target"


def test_indexed_write_reports_different_valid_frame_palettes_without_remap(
    tmp_path: Path, runtime
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode="indexed", palette_size=8)
    inject_palette_change(
        source, [(20 + i, 40, 60, 255) for i in range(8)], frame_number=2
    )
    code, result = run(
        "tilemap",
        "patch",
        **files(source, target, frame=2),
        patch={
            "entries": [
                {"tile_x": 0, "tile_y": 0, "placement": placement("d")},
            ]
        },
    )
    assert code == 0, json.dumps(result, indent=2)
    assert result["written_tiles"] == [
        {"tile_key": "d", "tile_index": 4, "palette_indexes": [4]}
    ]
    facts = result["effective_palettes"]
    assert [
        (f["frame_number"], f["palette_frame_number"], f["palette_size"]) for f in facts
    ] == [(1, 1, 8), (2, 2, 8)]
    assert all(
        [entry["index"] for entry in fact["indexes"]] == [4, 7] for fact in facts
    )
    assert facts[0]["indexes"][0]["color"] != facts[1]["indexes"][0]["color"]
    assert facts[1]["indexes"][0]["color"] == {
        "red": 24,
        "green": 40,
        "blue": 60,
        "alpha": 255,
    }
    code, tile = run(
        "tileset",
        "tile",
        "get",
        sprite_file=str(target),
        target={"tileset_index": 1},
        tile={"tile_key": "d"},
    )
    assert code == 0, tile
    assert all(
        row == [{"length": 2, "color": {"kind": "palette-index", "index": 4}}]
        for row in tile["snapshot"]["rows"]
    )


@pytest.mark.parametrize(
    "operation,inputs",
    [
        (
            "set",
            {
                "snapshot": {
                    "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                    "entries": [
                        {"tile_x": 0, "tile_y": 0, "placement": placement("a")}
                    ],
                }
            },
        ),
        (
            "patch",
            {
                "patch": {
                    "entries": [{"tile_x": 0, "tile_y": 0, "placement": placement("a")}]
                }
            },
        ),
        (
            "fill",
            {
                "coordinate_space": "tile-cell",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                "placement": placement("a"),
            },
        ),
    ],
)
def test_transparent_index_is_required_even_when_tile_does_not_use_it(
    tmp_path: Path, runtime, operation: str, inputs: dict
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode="indexed", palette_size=8)
    inject_palette_change(source, [(i, 40, 60, 255) for i in range(3)], frame_number=2)
    before = source.read_bytes()
    code, result = run("tilemap", operation, **files(source, target), **inputs)
    assert code == 2, result
    assert result["details"]["undefined_indexes"] == [7]
    assert result["details"]["frame_number"] == 2
    assert source.read_bytes() == before and not target.exists()


@pytest.mark.parametrize("frame", [1, 3])
def test_explicit_cel_creation_composes_with_keyed_set(
    tmp_path: Path, runtime, frame: int
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="cel_creation.lua")
    arguments = files(source, target, frame=frame)
    code, added = run("cel", "add", **arguments, tilemap_size={"width": 2, "height": 3})
    assert code == 0, added
    code, changed = run(
        "tilemap",
        "set",
        **files(target, target, frame=frame, in_place=True, overwrite=True),
        snapshot={
            "rectangle": {"x": 0, "y": 0, "width": 2, "height": 3},
            "entries": [
                {
                    "tile_x": 1,
                    "tile_y": 2,
                    "placement": placement("stone", flip_diagonal=True),
                }
            ],
        },
    )
    assert code == 0, changed
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target=arguments["target"],
        rectangle={"x": 0, "y": 0, "width": 2, "height": 3},
    )
    assert code == 0, observed
    assert observed["snapshot"]["entries"] == [
        {
            "tile_x": 1,
            "tile_y": 2,
            "placement": placement("stone", flip_diagonal=True) | {"tile_index": 1},
        }
    ]
