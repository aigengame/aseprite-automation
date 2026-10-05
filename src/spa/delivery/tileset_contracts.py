"""One Tileset atlas and one complete Tile Region Snapshot projection."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from spa.authoring.document.targets import CelAddress
from spa.authoring.tile.targets import TilesetTarget
from spa.authoring.tile.values import TilemapFacts, TileRegionSnapshot, TilesetFacts
from spa.contracts.mutation import validate_native_sprite_path
from spa.contracts.public import PublicModel, RuntimeRequest
from spa.contracts.raster import PositiveRectangle, RgbaColor
from spa.contracts.snapshot import SnapshotDestination
from spa.delivery.export import ExportDestination


class ExportTilesetRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    tileset: TilesetTarget
    target: CelAddress
    rectangle: PositiveRectangle
    columns: int = Field(ge=1, le=2147483647)
    image: ExportDestination
    metadata: SnapshotDestination
    _source = field_validator("source_sprite_file")(validate_native_sprite_path)


class EmptyAtlasTile(PublicModel):
    kind: Literal["empty"] = "empty"
    tile_index: Literal[0] = 0
    rectangle: PositiveRectangle


class KeyedAtlasTile(PublicModel):
    kind: Literal["tile"] = "tile"
    tile_index: int = Field(ge=1)
    tile_key: str = Field(min_length=1, pattern=r"^[^\x00]*$")
    rectangle: PositiveRectangle


AtlasTile = Annotated[EmptyAtlasTile | KeyedAtlasTile, Field(discriminator="kind")]


class AtlasProfile(PublicModel):
    kind: Literal["none", "srgb", "icc"]
    icc_identity: Literal["linear_srgb", "display_p3"] | None

    @model_validator(mode="after")
    def identity(self) -> "AtlasProfile":
        if (self.kind == "icc") != (self.icc_identity is not None):
            raise ValueError("ICC output requires an exact supported profile identity")
        return self


class AtlasPalette(PublicModel):
    frame_number: int = Field(ge=1)
    palette_frame_number: int = Field(ge=1)
    transparent_color_index: int = Field(ge=0, le=255)
    entries: list[RgbaColor] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def complete(self) -> "AtlasPalette":
        if self.palette_frame_number > self.frame_number:
            raise ValueError("Effective Palette change is after the selected Frame")
        if self.transparent_color_index >= len(self.entries):
            raise ValueError("PNG Palette omits the Transparent Color Index")
        if self.entries[self.transparent_color_index].alpha != 0:
            raise ValueError("PNG Transparent Color Index must have alpha zero")
        return self


class AtlasEncoding(PublicModel):
    bit_depth: Literal[8]
    color_type: Literal[0, 2, 3, 4, 6]


class TilesetAtlas(PublicModel):
    path: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    columns: int = Field(gt=0)
    color_mode: Literal["rgb", "grayscale", "indexed"]
    profile: AtlasProfile
    png: AtlasEncoding
    palette: AtlasPalette | None
    tiles: list[AtlasTile] = Field(min_length=1)

    @model_validator(mode="after")
    def representation(self) -> "TilesetAtlas":
        allowed = {"rgb": (2, 6), "grayscale": (0, 4), "indexed": (3,)}
        if self.png.color_type not in allowed[self.color_mode]:
            raise ValueError("PNG encoding differs from the source Color Mode")
        if (self.color_mode == "indexed") != (self.palette is not None):
            raise ValueError("Only Indexed PNG has encoded Palette facts")
        if self.color_mode == "grayscale" and self.profile.kind == "icc":
            raise ValueError("RGB ICC is unsupported in Grayscale PNG")
        if [tile.tile_index for tile in self.tiles] != list(range(len(self.tiles))):
            raise ValueError("Atlas must include every Tile in native index order")
        keys = [
            tile.tile_key for tile in self.tiles if isinstance(tile, KeyedAtlasTile)
        ]
        if len(set(keys)) != len(keys):
            raise ValueError("Each nonzero Tile requires a unique Tile Key")
        return self


class TilesetMap(PublicModel):
    schema_version: Literal[1] = 1
    source_sprite_file: str
    tileset: TilesetFacts
    tilemap: TilemapFacts
    snapshot: TileRegionSnapshot
    atlas: TilesetAtlas

    @model_validator(mode="after")
    def correspondence(self) -> "TilesetMap":
        atlas, grid, tilemap = self.atlas, self.tileset.grid, self.tilemap
        width, height = grid.tile_size.width, grid.tile_size.height
        if width <= 0 or height <= 0:
            raise ValueError("Tileset Grid must have positive Tile dimensions")
        if len(atlas.tiles) != self.tileset.tile_count:
            raise ValueError("Atlas must cover the full Tileset")
        rows = (self.tileset.tile_count + atlas.columns - 1) // atlas.columns
        if atlas.width != width * atlas.columns or atlas.height != height * rows:
            raise ValueError("Atlas dimensions differ from the explicit-column Grid")
        for tile in atlas.tiles:
            expected = PositiveRectangle(
                x=(tile.tile_index % atlas.columns) * width,
                y=(tile.tile_index // atlas.columns) * height,
                width=width,
                height=height,
            )
            if tile.rectangle != expected:
                raise ValueError("Atlas Tile rectangle differs from native index order")
        if not tilemap.exists or tilemap.tileset_index != self.tileset.tileset_index:
            raise ValueError("Map must select an existing Cel bound to this Tileset")
        assert tilemap.position is not None and tilemap.cell_size is not None
        assert (
            tilemap.effective_grid is not None and tilemap.canvas_coverage is not None
        )
        origin = tilemap.effective_grid.origin
        if (
            tilemap.effective_grid.tile_size != grid.tile_size
            or origin.x != grid.origin.x + tilemap.position.x
            or origin.y != grid.origin.y + tilemap.position.y
            or tilemap.canvas_coverage
            != PositiveRectangle(
                x=origin.x,
                y=origin.y,
                width=tilemap.cell_size.width * width,
                height=tilemap.cell_size.height * height,
            )
            or tilemap.layer not in self.tileset.layers
        ):
            raise ValueError(
                "Tilemap binding or effective Grid mapping is inconsistent"
            )
        area = self.snapshot.rectangle
        if (
            area.x + area.width > tilemap.cell_size.width
            or area.y + area.height > tilemap.cell_size.height
        ):
            raise ValueError("Complete Tile Region extends outside the Cel")
        for entry in self.snapshot.entries:
            placement = entry.placement
            if not 0 < placement.tile_index < len(atlas.tiles):
                raise ValueError("Non-empty map placement must select a keyed Tile")
            tile = atlas.tiles[placement.tile_index]
            if (
                not isinstance(tile, KeyedAtlasTile)
                or placement.tile_key != tile.tile_key
            ):
                raise ValueError("Map Tile Key differs from atlas identity")
        if (
            atlas.palette is not None
            and atlas.palette.frame_number != tilemap.frame_number
        ):
            raise ValueError("Indexed export must use the selected map Frame's Palette")
        return self


class TilesetArtifact(PublicModel):
    role: Literal["tileset-image", "map-data"]
    path: str
    media_type: Literal["image/png", "application/json"]
    format: Literal["png", "json"]
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExportTilesetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa export tileset"] = "spa export tileset"
    image: ExportDestination
    metadata: SnapshotDestination
    map: TilesetMap
    artifacts: list[TilesetArtifact] = Field(min_length=2, max_length=2)


class NativeTilesetExport(PublicModel):
    metadata: TilesetMap
    tile_digests: list[Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]]
