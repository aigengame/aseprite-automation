"""Explicit Tilemap Cel creation inputs and native evidence."""

from collections.abc import Sequence
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from spa.authoring.document.cel_contracts import CelState
from spa.authoring.tile.values import TilemapFacts, TilesetFacts
from spa.contracts.ports import (
    PackagedResource,
    RuntimeCompatibilityEvidence,
    RuntimeIssue,
    RuntimeObservation,
)
from spa.contracts.public import CapabilityGap, PublicModel
from spa.contracts.raster import Point, Size

MAX_TILEMAP_CELLS = 1_048_576
TILE_CEL_RESOURCE = PackagedResource("tile_cel_add", "tile/cel_add.lua")


def require_tilemap_creation(runtime: RuntimeObservation) -> None:
    if "aseprite_tile_cel_creation" not in runtime.verified_capabilities:
        raise RuntimeIssue(
            "runtime_incompatible",
            "The selected runtime did not verify empty Tilemap Cel creation",
            RuntimeCompatibilityEvidence(
                aseprite_version=runtime.aseprite_version,
                lua_version=runtime.lua_version,
                api_version=runtime.api_version,
                required_lua_language="Lua 5.4",
                minimum_api_version=41,
                missing_capabilities=("aseprite_tile_cel_creation",),
            ),
        )


def tilemap_creation_gaps(
    version: str, capabilities: Sequence[str]
) -> list[CapabilityGap]:
    if "aseprite_tile_cel_creation" in capabilities:
        return []
    return [
        CapabilityGap(
            capability="spa cel add: Tilemap Cel creation",
            aseprite_version=version,
            evidence="The selected runtime did not pass empty Tilemap Cel save/reopen. "
            "Requests with tilemap_size require this capability; ordinary Cel creation is independent.",
        )
    ]


class TilemapSize(PublicModel):
    """Initial Tile Cell dimensions: sides 1..65535, at most 1,048,576 Cells total."""

    model_config = ConfigDict(
        json_schema_extra={"x-spa-max-tile-cells": MAX_TILEMAP_CELLS}
    )
    width: int = Field(ge=1, le=65535, strict=True)
    height: int = Field(ge=1, le=65535, strict=True)

    @model_validator(mode="after")
    def bounded_cells(self) -> "TilemapSize":
        if self.width * self.height > MAX_TILEMAP_CELLS:
            raise ValueError(
                f"Tilemap size exceeds the {MAX_TILEMAP_CELLS}-Tile Cell Operation Limit"
            )
        return self


class TilemapCreationEvidence(PublicModel):
    tilemap: TilemapFacts
    tileset: TilesetFacts
    empty_tile_cells_verified: Literal[True]

    def matches(self, size: TilemapSize, cel: CelState) -> bool:
        facts, tileset = self.tilemap, self.tileset
        grid, coverage = facts.effective_grid, facts.canvas_coverage
        return (
            cel.is_tilemap
            and facts.exists
            and facts.layer.layer_path == cel.layer_path
            and facts.frame_number == cel.frame_number
            and facts.position == cel.position
            and facts.cell_size == Size(width=size.width, height=size.height)
            and facts.tileset_index == tileset.tileset_index
            and facts.layer in tileset.layers
            and grid is not None
            and grid.tile_size == tileset.grid.tile_size
            and grid.origin == tileset.grid.origin
            and coverage is not None
            and Point(x=coverage.x, y=coverage.y) == grid.origin
            and coverage.width == size.width * grid.tile_size.width
            and coverage.height == size.height * grid.tile_size.height
        )
