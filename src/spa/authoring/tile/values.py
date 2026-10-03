"""Tile identities, topology, and complete bounded observation values."""

from typing import Literal

from pydantic import Field, model_validator

from spa.authoring.tile.properties import PropertyNamespace
from spa.contracts.public import PublicModel
from spa.contracts.raster import Point, PositiveRectangle, RgbaColor, Size


class TileGrid(PublicModel):
    origin: Point
    tile_size: Size


class TilemapLayer(PublicModel):
    layer_path: list[int] = Field(min_length=1)
    layer_uuid: str | None
    name: str


class TilesetFacts(PublicModel):
    tileset_index: int = Field(ge=1)
    name: str
    base_index: int
    tile_count: int = Field(ge=1)
    grid: TileGrid
    layers: list[TilemapLayer]


class TileFacts(PublicModel):
    tile_index: int = Field(ge=0)
    tile_key: str | None
    display_index: int
    image_size: Size
    color_mode: Literal["rgb", "grayscale", "indexed"]
    data: str
    color: RgbaColor
    properties: list[PropertyNamespace]


class TilemapFacts(PublicModel):
    layer: TilemapLayer
    tileset_index: int = Field(ge=1)
    frame_number: int = Field(ge=1)
    exists: bool
    position: Point | None
    cell_size: Size | None
    effective_grid: TileGrid | None
    canvas_coverage: PositiveRectangle | None

    @model_validator(mode="after")
    def presence(self) -> "TilemapFacts":
        facts = (
            self.position,
            self.cell_size,
            self.effective_grid,
            self.canvas_coverage,
        )
        if any((value is not None) != self.exists for value in facts):
            raise ValueError("Tilemap Cel presence differs from its geometry")
        return self


class EmptyPlacement(PublicModel):
    kind: Literal["empty"] = "empty"


class ObservedTilePlacement(PublicModel):
    kind: Literal["tile"] = "tile"
    tile_index: int = Field(ge=0)
    tile_key: str | None
    flip_x: bool
    flip_y: bool
    flip_diagonal: bool

    @model_validator(mode="after")
    def empty_tile(self) -> "ObservedTilePlacement":
        if self.tile_index == 0:
            if self.tile_key is not None:
                raise ValueError("Empty Tile 0 has no Tile Key")
            if not (self.flip_x or self.flip_y or self.flip_diagonal):
                raise ValueError("An unflagged index-0 Cell uses the empty default")
        return self


class TileRegionEntry(PublicModel):
    tile_x: int = Field(ge=0)
    tile_y: int = Field(ge=0)
    placement: ObservedTilePlacement


class TileRegionSnapshot(PublicModel):
    coordinate_space: Literal["tile-cell"] = "tile-cell"
    rectangle: PositiveRectangle
    complete: Literal[True] = True
    default: EmptyPlacement = Field(default_factory=EmptyPlacement)
    entries: list[TileRegionEntry]

    @model_validator(mode="after")
    def canonical(self) -> "TileRegionSnapshot":
        area, previous = self.rectangle, (-1, -1)
        if area.x < 0 or area.y < 0:
            raise ValueError("Tile Region origin must be Cel-local and nonnegative")
        for entry in self.entries:
            current = (entry.tile_y, entry.tile_x)
            if current <= previous:
                raise ValueError("Tile entries must be unique and in row-major order")
            if not (
                area.x <= entry.tile_x < area.x + area.width
                and area.y <= entry.tile_y < area.y + area.height
            ):
                raise ValueError(
                    "Tile entry is outside the declared complete Rectangle"
                )
            previous = current
        return self


class TileFinding(PublicModel):
    code: Literal[
        "tile_key_missing",
        "tile_key_duplicate",
        "tile_key_invalid",
        "empty_tile_flags",
        "tile_index_out_of_bounds",
        "tile_image_grid_mismatch",
    ]
    tileset_index: int = Field(ge=1)
    tile_index: int = Field(ge=0)
    tile_key: str | None = None
    layer_path: list[int] | None = None
    frame_number: int | None = None
    tile_x: int | None = None
    tile_y: int | None = None
