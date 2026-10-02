"""Read-only Tile Authoring operations over one native Sprite snapshot."""

from typing import Literal

from pydantic import Field, ValidationError, field_validator

from spa.authoring.document.sprite import SPRITE_INSPECTION_RESOURCES
from spa.contracts.mutation import validate_native_sprite_path
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import PublicModel, RuntimeRequest, RuntimeRequirements
from spa.contracts.raster import Point, Size

TILE_PROBE_RESOURCE = PackagedResource("tile_probe", "tile/probe.lua")
TILE_INSPECTION_RESOURCE = PackagedResource("tile_inspection", "tile/inspection.lua")
TILE_READ_HANDLER = PackagedHandler(
    "tile_read",
    "tile/read.lua",
    (*SPRITE_INSPECTION_RESOURCES, TILE_INSPECTION_RESOURCE),
)
TILE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_tile_inspection"],
)


class TileGrid(PublicModel):
    origin: Point
    tile_size: Size


class TilemapLayer(PublicModel):
    layer_path: list[int]
    name: str


class TilesetFacts(PublicModel):
    tileset_index: int = Field(ge=1)
    name: str
    base_index: int
    tile_count: int = Field(ge=1)
    grid: TileGrid
    layers: list[TilemapLayer]


class TilesetListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)
    _source = field_validator("sprite_file")(validate_native_sprite_path)


class TilesetListResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset list"] = "spa tileset list"
    sprite_file: str
    complete: Literal[True] = True
    tilesets: list[TilesetFacts]


def list_tilesets(
    request: TilesetListRequest, services: OperationServices
) -> TilesetListResult:
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        TILE_READ_HANDLER,
        {"operation": "tileset list", "sprite_file": request.sprite_file},
        request.timeout_seconds,
    )
    try:
        return TilesetListResult.model_validate(invocation.payload)
    except ValidationError as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Invalid Tileset inspection",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc


TILE_OPERATIONS = (
    OperationDescriptor(
        "tileset list",
        TilesetListRequest,
        TilesetListResult,
        list_tilesets,
        lambda result: f"{len(result.tilesets)} Tilesets",
        TILE_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
)
