"""Tile addresses and typed target failures shared by reads and authoring."""

from typing import Literal

from pydantic import Field, model_validator

from spa.authoring.document.targets import CelAddress, LayerAddress
from spa.contracts.ports import PackagedResource
from spa.contracts.public import FailureCodeSpec, PublicModel
from spa.contracts.raster import PositiveRectangle

TILESET_RESOURCE = PackagedResource("tilesets", "tile/tilesets.lua")
TILE_KEY_RESOURCE = PackagedResource("tile_keys", "tile/keys.lua")


class TilesetTarget(PublicModel):
    """One current Tileset address or one Layer binding."""

    tileset_index: int | None = Field(default=None, ge=1, strict=True)
    tileset_name: str | None = Field(default=None, pattern=r"^[^\x00]*$")
    layer: LayerAddress | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> "TilesetTarget":
        if (
            sum(
                value is not None
                for value in (self.tileset_index, self.tileset_name, self.layer)
            )
            != 1
        ):
            raise ValueError(
                "Specify exactly one Tileset index, name, or Tilemap Layer"
            )
        return self


class TileAddress(PublicModel):
    tile_index: int | None = Field(default=None, ge=0, strict=True)
    tile_key: str | None = Field(default=None, min_length=1, pattern=r"^[^\x00]*$")

    @model_validator(mode="after")
    def exactly_one(self) -> "TileAddress":
        if (self.tile_index is None) == (self.tile_key is None):
            raise ValueError("Specify exactly one current Tile index or Tile Key")
        return self


class TileSnapshotLimit(PublicModel):
    unit: Literal["pixels", "tile_cells"]
    maximum_inline: int = Field(gt=0)
    requested: int = Field(gt=0)


class TileInspectionDetails(PublicModel):
    kind: Literal["tile_inspection"] = "tile_inspection"
    target: TilesetTarget | CelAddress | None = None
    tile: TileAddress | None = None
    rectangle: PositiveRectangle | None = None
    snapshot_limit: TileSnapshotLimit | None = None


TILE_FAILURE_SPECS = tuple(
    FailureCodeSpec(code, description, "input", TileInspectionDetails)
    for code, description in (
        ("tileset_missing", "No Tileset matches the current address or binding"),
        ("tileset_ambiguous", "Tileset name matches more than one Tileset"),
        ("tilemap_layer_required", "The selected Layer is not a Tilemap Layer"),
        ("tile_key_missing", "No Tile has the requested Tile Key"),
        ("tile_key_ambiguous", "More than one Tile has the requested Tile Key"),
        ("tile_index_out_of_bounds", "The current Tile index is outside the Tileset"),
        ("tilemap_frame_out_of_bounds", "The requested Frame is outside the timeline"),
        ("tilemap_cel_missing", "The requested Tilemap Cel does not exist"),
        (
            "tile_region_out_of_bounds",
            "The requested Rectangle exceeds the Tilemap Image",
        ),
        (
            "tile_snapshot_destination_required",
            "The complete Snapshot exceeds the inline limit; provide a JSON destination",
        ),
    )
)
