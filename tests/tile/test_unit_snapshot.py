"""Canonical complete Tile Region Snapshots and exact public addressing."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from spa.authoring.tile.inspection import TileAddress, TilemapGetRequest, TilesetTarget
from spa.authoring.tile.values import TileRegionSnapshot


def snapshot() -> dict:
    return {
        "coordinate_space": "tile-cell",
        "rectangle": {"x": 2, "y": 3, "width": 2, "height": 2},
        "complete": True,
        "default": {"kind": "empty"},
        "entries": [
            {
                "tile_x": 2,
                "tile_y": 3,
                "placement": {
                    "kind": "tile",
                    "tile_key": None,
                    "tile_index": 1,
                    "flip_x": False,
                    "flip_y": True,
                    "flip_diagonal": False,
                },
            }
        ],
    }


@pytest.mark.parametrize(
    "defect",
    [
        "duplicate",
        "order",
        "outside",
        "empty-entry",
        "packed",
        "incomplete",
        "negative-origin",
    ],
)
def test_snapshot_rejects_ambiguous_or_incomplete_representation(defect: str) -> None:
    value = snapshot()
    entry = value["entries"][0]
    if defect == "duplicate":
        value["entries"].append(deepcopy(entry))
    elif defect == "order":
        second = deepcopy(entry)
        second["tile_y"] = 4
        value["entries"].insert(0, second)
    elif defect == "outside":
        entry["tile_x"] = 4
    elif defect == "empty-entry":
        entry["placement"] = {"kind": "empty"}
    elif defect == "packed":
        entry["placement"] = 0x80000001
    elif defect == "incomplete":
        value["complete"] = False
    else:
        value["rectangle"]["x"] = -1
    with pytest.raises(ValidationError):
        TileRegionSnapshot.model_validate(value)


def test_unkeyed_observation_and_nonzero_region_origin_are_not_lossy() -> None:
    assert TileRegionSnapshot.model_validate(snapshot()).model_dump() == snapshot()


@pytest.mark.parametrize(
    "target",
    [
        {},
        {"tileset_index": 1, "tileset_name": "terrain"},
        {"tileset_index": 1, "layer": {"layer_path": [2]}},
        {"base_index": 1},
        {"tileset_index": True},
    ],
)
def test_tileset_requires_one_current_address(target: dict) -> None:
    with pytest.raises(ValidationError):
        TilesetTarget.model_validate(target)


@pytest.mark.parametrize(
    "address",
    [{}, {"tile_index": 1, "tile_key": "grass"}, {"tile_key": ""}, {"tile_index": -1}],
)
def test_tile_requires_one_key_or_observation_index(address: dict) -> None:
    with pytest.raises(ValidationError):
        TileAddress.model_validate(address)


def test_summary_cannot_publish_an_undeclared_region() -> None:
    with pytest.raises(ValidationError, match="explicit Tile Cell Rectangle"):
        TilemapGetRequest.model_validate(
            {
                "sprite_file": "source.aseprite",
                "target": {"layer": {"layer_path": [2]}, "frame_number": 1},
                "snapshot_destination": {"path": "map.json", "if_exists": "fail"},
            }
        )
