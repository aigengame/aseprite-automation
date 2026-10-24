"""Tile lifecycle request models refuse a Tile address or Key list that cannot work."""

import pytest
from pydantic import ValidationError

from spa.authoring.tile.lifecycle import TileAssignKeyRequest, TileReorderRequest


def _request(**values: object) -> dict:
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": True,
        "target": {"tileset_index": 1},
        **values,
    }


def test_assign_key_refuses_the_empty_tile_at_index_zero() -> None:
    TileAssignKeyRequest.model_validate(_request(tile_index=1, tile_key="new"))
    with pytest.raises(ValidationError) as refused:
        TileAssignKeyRequest.model_validate(_request(tile_index=0, tile_key="new"))
    assert [error["loc"] for error in refused.value.errors()] == [("tile_index",)]


def test_reorder_refuses_a_duplicate_tile_key() -> None:
    TileReorderRequest.model_validate(_request(tile_keys=["a", "b", "c"]))
    with pytest.raises(ValidationError) as refused:
        TileReorderRequest.model_validate(_request(tile_keys=["a", "b", "c", "c"]))
    assert [error["loc"] for error in refused.value.errors()] == [("tile_keys",)]
    assert "exactly once" in refused.value.errors()[0]["msg"]
