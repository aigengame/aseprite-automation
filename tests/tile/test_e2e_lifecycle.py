"""Keyed Tile lifecycle through the public SPA interface and persisted native data."""

import json
from pathlib import Path

import pytest

from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


def files(source: Path, target: Path, **extra: object) -> dict:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": source == target,
        "overwrite": source == target,
        "target": {"tileset_index": 1},
        **extra,
    }


def snapshot(mode: str = "rgb", *, transparent: bool = False) -> dict:
    color = {
        "rgb": {
            "kind": "rgba",
            "red": 17,
            "green": 29,
            "blue": 41,
            "alpha": 0 if transparent else 255,
        },
        "grayscale": {
            "kind": "grayscale",
            "gray": 79,
            "alpha": 0 if transparent else 255,
        },
        "indexed": {"kind": "palette-index", "index": 7 if transparent else 2},
    }[mode]
    return {
        "coordinate_space": "image-pixel",
        "color_mode": mode,
        "rectangle": {"x": 0, "y": 0, "width": 2, "height": 3},
        "rows": [[{"length": 2, "color": color}] for _ in range(3)],
    }


def test_add_appends_explicit_complete_image_and_key(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "added.aseprite"
    fixture(source, runtime)
    original = source.read_bytes()
    image = snapshot()
    code, added = run(
        "tileset", "tile", "add", **files(source, target), tile_key="new", image=image
    )
    assert code == 0, added
    assert added["tile"] == {"tile_index": 5, "tile_key": "new"}
    assert added["persisted_reopen_verified"] is True
    assert added["affected_cels"] == []
    code, observed = run(
        "tileset",
        "tile",
        "get",
        sprite_file=str(target),
        target={"tileset_index": 1},
        tile={"tile_key": "new"},
    )
    assert code == 0, observed
    assert observed["snapshot"] == image
    assert source.read_bytes() == original


def test_assign_missing_key_preserves_native_metadata(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "keyed.aseprite"
    fixture(source, runtime, script="lifecycle.lua", unkeyed="3")
    original = source.read_bytes()
    code, assigned = run(
        "tileset",
        "tile",
        "assign-key",
        **files(source, target),
        tile_index=3,
        tile_key="c",
    )
    assert code == 0, assigned
    assert assigned["tile"] == {"tile_index": 3, "tile_key": "c"}
    assert assigned["affected_cels"] == []
    fixture(
        target, runtime, script="verify_lifecycle.lua", order=json.dumps([1, 2, 3, 4])
    )
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "replacement,order,cells",
    [
        ({"kind": "empty"}, [1, 3, 4], [1, None, 2, 3]),
        ({"kind": "tile", "tile_key": "d"}, [1, 3, 4], [1, 3, 2, 3]),
        ({"kind": "tile", "tile_key": "a"}, [1, 3, 4], [1, 1, 2, 3]),
    ],
)
def test_remove_maps_all_linked_and_shared_placements(
    tmp_path: Path, runtime, replacement: dict, order: list, cells: list
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "removed.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    original = source.read_bytes()
    code, removed = run(
        "tileset",
        "tile",
        "remove",
        **files(source, target),
        tile_key="b",
        replacement=replacement,
    )
    assert code == 0, removed
    assert len(removed["affected_cels"]) == 3
    assert len(removed["affected_layers"]) == 2
    assert [item["new_index"] for item in removed["index_mapping"]] == [
        0,
        1,
        cells[1] or 0,
        2,
        3,
    ]
    packed = [0 if index is None else index | 0xE0000000 for index in cells] + [
        0xE0000000
    ]
    fixture(
        target,
        runtime,
        script="verify_lifecycle.lua",
        order=json.dumps(order),
        cells=json.dumps(packed),
    )
    assert source.read_bytes() == original


def test_reorder_preserves_keys_images_flags_and_native_properties(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "reordered.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    original = source.read_bytes()
    code, result = run(
        "tileset",
        "tile",
        "reorder",
        **files(source, target),
        tile_keys=["d", "b", "a", "c"],
    )
    assert code == 0, result
    assert [item["new_index"] for item in result["index_mapping"]] == [0, 3, 2, 4, 1]
    assert [item["changed_cells"] for item in result["affected_cels"]] == [3, 3, 3]
    fixture(
        target,
        runtime,
        script="verify_lifecycle.lua",
        order=json.dumps([4, 2, 1, 3]),
        cells=json.dumps([index | 0xE0000000 for index in [3, 2, 4, 1, 0]]),
    )
    assert source.read_bytes() == original
