"""Bounded Tile Cell writes with native Linked Cel and publication semantics."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.document.cel_contracts import (
    CEL_SUPPORT_RESOURCE,
    CelMutationRequest,
    CelState,
)
from spa.authoring.document.sprite import (
    SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteInspection,
)
from spa.authoring.document.targets import (
    LAYER_ADDRESS_FAILURE_CODES,
    CelAddress,
    LayerTargetDetails,
)
from spa.authoring.tile.targets import (
    TILE_KEY_RESOURCE,
    TILEMAP_RESOURCE,
    TILESET_RESOURCE,
    TileAddress,
    TileInspectionDetails,
)
from spa.authoring.tile.values import EmptyPlacement, TilemapFacts
from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import TargetCommit
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequirements
from spa.contracts.raster import (
    RASTER_COLOR_RESOURCE,
    EffectivePaletteFact,
    ImageContentDigest,
    PositiveRectangle,
)

TILE_REGION_LIMITS = {"tile_cells": 1_048_576, "entries": 4096}


class KeyedTilePlacement(PublicModel):
    kind: Literal["tile"] = "tile"
    tile_key: str = Field(min_length=1, pattern=r"^[^\x00]*$")
    flip_x: bool
    flip_y: bool
    flip_diagonal: bool


TilePlacement = Annotated[
    EmptyPlacement | KeyedTilePlacement, Field(discriminator="kind")
]


class KeyedTileRegionEntry(PublicModel):
    tile_x: int = Field(ge=0)
    tile_y: int = Field(ge=0)
    placement: KeyedTilePlacement


class TileRegionInput(PublicModel):
    """Complete sparse replacement: every omitted Cell becomes Empty."""

    coordinate_space: Literal["tile-cell"] = "tile-cell"
    rectangle: PositiveRectangle
    complete: Literal[True] = True
    default: EmptyPlacement = Field(default_factory=EmptyPlacement)
    entries: list[KeyedTileRegionEntry] = Field(
        max_length=TILE_REGION_LIMITS["entries"]
    )

    @model_validator(mode="after")
    def canonical_entries(self) -> "TileRegionInput":
        area = self.rectangle
        if area.x < 0 or area.y < 0:
            raise ValueError("Tile Cell Rectangle origin must be nonnegative")
        coordinates = [(item.tile_y, item.tile_x) for item in self.entries]
        if coordinates != sorted(set(coordinates)):
            raise ValueError("Snapshot entries must be unique and in row-major order")
        if any(
            not (
                area.x <= x < area.x + area.width and area.y <= y < area.y + area.height
            )
            for y, x in coordinates
        ):
            raise ValueError("Snapshot entry is outside its declared Rectangle")
        return self


class TilemapMutationRequest(CelMutationRequest):
    """Write one existing Cel Image; preserve native Linked Cels."""

    model_config = ConfigDict(
        json_schema_extra={"x-spa-operation-limits": {**TILE_REGION_LIMITS}}
    )


class TilemapSetRequest(TilemapMutationRequest):
    """Replace a complete Rectangle; omitted Cells become Empty."""

    snapshot: TileRegionInput


class TilemapPatchEntry(PublicModel):
    tile_x: int = Field(ge=0)
    tile_y: int = Field(ge=0)
    placement: TilePlacement


class TilemapPatch(PublicModel):
    """Unique explicit Cells; omitted coordinates keep their existing Placement."""

    coordinate_space: Literal["tile-cell"] = "tile-cell"
    entries: list[TilemapPatchEntry] = Field(max_length=TILE_REGION_LIMITS["entries"])

    @model_validator(mode="after")
    def unique_coordinates(self) -> "TilemapPatch":
        if len({(item.tile_x, item.tile_y) for item in self.entries}) != len(
            self.entries
        ):
            raise ValueError("Patch entries must have unique Tile Cell coordinates")
        return self


class TilemapPatchRequest(TilemapMutationRequest):
    """Change only the explicit Cells, without clipping or implicit Cel creation."""

    patch: TilemapPatch


class TilemapFillRequest(TilemapMutationRequest):
    """Fill a complete Tile Cell Rectangle with one Placement."""

    coordinate_space: Literal["tile-cell"]
    rectangle: PositiveRectangle
    placement: TilePlacement


type TilemapRequest = TilemapSetRequest | TilemapPatchRequest | TilemapFillRequest


class WrittenTile(PublicModel):
    tile_key: str = Field(min_length=1)
    tile_index: int = Field(ge=1)
    palette_indexes: list[Annotated[int, Field(ge=0, le=255)]]


class TilemapRegionEvidence(PublicModel):
    tilemap: TilemapFacts
    affected_cels: list[CelState] = Field(min_length=1)
    cells_written: int = Field(ge=0)
    cells_changed: int = Field(ge=0)
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest
    written_tiles: list[WrittenTile]
    effective_palettes: list[EffectivePaletteFact]
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]


class TilemapSetResult(TilemapRegionEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa tilemap set"] = "spa tilemap set"
    target_commit: TargetCommit


class TilemapPatchResult(TilemapRegionEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa tilemap patch"] = "spa tilemap patch"
    target_commit: TargetCommit


class TilemapFillResult(TilemapRegionEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa tilemap fill"] = "spa tilemap fill"
    target_commit: TargetCommit


def _rectangle(request: TilemapRequest) -> PositiveRectangle | None:
    if isinstance(request, TilemapSetRequest):
        return request.snapshot.rectangle
    if isinstance(request, TilemapFillRequest):
        return request.rectangle
    return None


class TilemapRegionDetails(PublicModel):
    kind: Literal["tilemap_region"] = "tilemap_region"
    target: CelAddress
    reason: Literal["tile_cells_limit", "palette_incompatible"]
    message: str
    frame_number: int | None = Field(default=None, ge=1)
    palette_frame_number: int | None = Field(default=None, ge=1)
    palette_size: int | None = Field(default=None, ge=1)
    undefined_indexes: list[Annotated[int, Field(ge=0, le=255)]] = Field(
        default_factory=list
    )


TILE_REGION_FAILURE_SPECS = (
    FailureCodeSpec(
        "tilemap_region_invalid",
        "Tilemap region exceeds operation bounds or Palette compatibility",
        "input",
        TilemapRegionDetails,
    ),
)
_TARGET_CODES = (
    "tilemap_layer_required",
    "tilemap_frame_out_of_bounds",
    "tilemap_cel_missing",
    "tile_region_out_of_bounds",
    "tile_key_missing",
    "tile_key_ambiguous",
)
TILE_REGION_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    *LAYER_ADDRESS_FAILURE_CODES,
    *_TARGET_CODES,
    "tilemap_region_invalid",
    "target_commit_failed",
)
TILE_REGION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_sprite_inspection",
        "aseprite_tile_inspection",
        "aseprite_tile_lifecycle",
    ],
)
TILE_REGION_HANDLER = PackagedHandler(
    "tilemap_mutate",
    "tile/region_mutate.lua",
    (
        *SPRITE_INSPECTION_RESOURCES,
        TILESET_RESOURCE,
        TILEMAP_RESOURCE,
        TILE_KEY_RESOURCE,
        PackagedResource("tile_properties", "tile/properties.lua"),
        EFFECTIVE_PALETTE_RESOURCE,
        RASTER_COLOR_RESOURCE,
        CEL_SUPPORT_RESOURCE,
        SPRITE_PERSISTENCE_RESOURCE,
        DIGEST_RESOURCE,
        PackagedResource("tile_regions", "tile/regions.lua"),
    ),
)


def _reject(invocation: KernelInvocationResult, request: TilemapRequest) -> None:
    rejected = invocation.payload.get("rejection")
    if rejected is None:
        return
    if not isinstance(rejected, dict) or not isinstance(rejected.get("message"), str):
        raise TypeError("Invalid Tilemap region rejection")
    code, message = rejected.get("code"), rejected["message"]
    if code == "tilemap_region_invalid":
        details = TilemapRegionDetails(
            target=request.target,
            reason=rejected["reason"],
            message=message,
            frame_number=rejected.get("frame_number"),
            palette_frame_number=rejected.get("palette_frame_number"),
            palette_size=rejected.get("palette_size"),
            undefined_indexes=rejected.get("undefined_indexes", []),
        )
    elif code in LAYER_ADDRESS_FAILURE_CODES:
        details = LayerTargetDetails(
            address_role="target", address=request.target.layer
        )
    elif code in _TARGET_CODES:
        details = TileInspectionDetails(
            target=request.target,
            rectangle=_rectangle(request),
            tile=TileAddress(tile_key=rejected["tile_key"])
            if "tile_key" in rejected
            else None,
        )
    else:
        raise ValueError("Unknown Tilemap region rejection")
    raise OperationIssue(code, message, details)


def _validate_evidence(request: TilemapRequest, result: TilemapRegionEvidence) -> None:
    facts, address = result.tilemap, request.target
    layer = facts.layer
    if (
        not facts.exists
        or facts.frame_number != address.frame_number
        or (
            address.layer.layer_path is not None
            and layer.layer_path != address.layer.layer_path
        )
        or (
            address.layer.layer_uuid is not None
            and layer.layer_uuid != address.layer.layer_uuid
        )
        or (
            address.layer.layer_name is not None
            and layer.name != address.layer.layer_name
        )
    ):
        raise ValueError("Tilemap evidence differs from the requested target")
    area = _rectangle(request)
    written = (
        len(request.patch.entries)
        if isinstance(request, TilemapPatchRequest)
        else area.width * area.height
        if area is not None
        else -1
    )
    if result.cells_written != written or result.cells_changed > result.cells_written:
        raise ValueError("Tile Cell write counts differ from requested coverage")
    if (result.cells_changed == 0) != (
        result.before_content_digest == result.after_content_digest
    ):
        raise ValueError("Changed Cell count contradicts content digests")
    tilesets = result.sprite.tilesets or []
    if facts.tileset_index > len(tilesets):
        raise ValueError("Tilemap binding is outside the persisted Tileset collection")
    tileset = tilesets[facts.tileset_index - 1]
    size, position, grid, coverage = (
        facts.cell_size,
        facts.position,
        facts.effective_grid,
        facts.canvas_coverage,
    )
    if size is None or position is None or grid is None or coverage is None:
        raise ValueError("Existing Tilemap Cel has incomplete geometry")
    if (
        size.width < 1
        or size.height < 1
        or size.width * size.height > TILE_REGION_LIMITS["tile_cells"]
        or grid.tile_size != tileset.tile_size
        or grid.origin.x != position.x + tileset.grid_origin.x
        or grid.origin.y != position.y + tileset.grid_origin.y
        or coverage.x != grid.origin.x
        or coverage.y != grid.origin.y
        or coverage.width != size.width * grid.tile_size.width
        or coverage.height != size.height * grid.tile_size.height
        or (
            area is not None
            and (
                area.x < 0
                or area.y < 0
                or area.x + area.width > size.width
                or area.y + area.height > size.height
            )
        )
        or (
            isinstance(request, TilemapPatchRequest)
            and any(
                entry.tile_x >= size.width or entry.tile_y >= size.height
                for entry in request.patch.entries
            )
        )
    ):
        raise ValueError("Tile Cell coverage differs from persisted Tilemap geometry")
    addresses = {
        (tuple(cel.layer_path), cel.frame_number) for cel in result.affected_cels
    }
    if (
        len(addresses) != len(result.affected_cels)
        or (tuple(layer.layer_path), facts.frame_number) not in addresses
    ):
        raise ValueError("Affected Cels are duplicated or omit the selected Cel")
    for cel in result.affected_cels:
        own = (tuple(cel.layer_path), cel.frame_number)
        links = {
            (tuple(link.layer_path), link.frame_number) for link in cel.linked_cels
        }
        if (
            not cel.exists
            or not cel.is_tilemap
            or links != addresses - {own}
            or len(links) != len(cel.linked_cels)
        ):
            raise ValueError(
                "Affected Cel evidence does not preserve complete Image sharing"
            )
        actual = [
            item
            for item in result.sprite.cels or []
            if (tuple(item.layer_path), item.frame_number) == own
        ]
        if (
            len(actual) != 1
            or cel.position is None
            or actual[0].bounds.x != cel.position.x
            or actual[0].bounds.y != cel.position.y
            or actual[0].opacity != cel.opacity
            or actual[0].z_index != cel.z_index
            or actual[0].bounds.width != coverage.width
            or actual[0].bounds.height != coverage.height
            or (
                cel.layer_path == layer.layer_path
                and cel.frame_number == facts.frame_number
                and cel.position != position
            )
        ):
            raise ValueError("Affected Cel differs from persisted Sprite inspection")
    placements = (
        [request.placement]
        if isinstance(request, TilemapFillRequest)
        else [entry.placement for entry in request.snapshot.entries]
        if isinstance(request, TilemapSetRequest)
        else [entry.placement for entry in request.patch.entries]
    )
    keys = {
        item.tile_key for item in placements if isinstance(item, KeyedTilePlacement)
    }
    if (
        len(result.written_tiles) != len(keys)
        or {tile.tile_key for tile in result.written_tiles} != keys
        or len({tile.tile_index for tile in result.written_tiles}) != len(keys)
        or any(tile.tile_index >= tileset.tile_count for tile in result.written_tiles)
    ):
        raise ValueError("Written Tile identities differ from requested Keys")
    used = {result.sprite.metadata.transparent_color_index}
    for tile in result.written_tiles:
        if tile.palette_indexes != sorted(set(tile.palette_indexes)):
            raise ValueError("Tile Palette indexes must be unique and sorted")
        used.update(tile.palette_indexes)
    if result.sprite.metadata.color_mode != "indexed" or not keys:
        if result.effective_palettes or any(
            tile.palette_indexes for tile in result.written_tiles
        ):
            raise ValueError(
                "Palette basis is only applicable to non-empty Indexed writes"
            )
        return
    frames = {cel.frame_number for cel in result.affected_cels}
    if (
        len(result.effective_palettes) != len(frames)
        or {fact.frame_number for fact in result.effective_palettes} != frames
    ):
        raise ValueError("Palette evidence must cover every affected Frame")
    for fact in result.effective_palettes:
        palette = max(
            (
                p
                for p in result.sprite.palettes or []
                if p.frame_number <= fact.frame_number
            ),
            key=lambda p: p.frame_number,
        )
        if (
            fact.palette_frame_number != palette.frame_number
            or fact.palette_size != len(palette.entries)
            or [item.index for item in fact.indexes] != sorted(used)
            or any(
                item.index >= len(palette.entries)
                or item.color != palette.entries[item.index].color
                for item in fact.indexes
            )
        ):
            raise ValueError("Indexed Tile basis differs from persisted Frame Palette")


def _mutate[T: TilemapRegionEvidence](
    request: TilemapRequest,
    services: OperationServices,
    operation: str,
    result_type: type[T],
) -> T:
    completion = prepare_mutation(
        services.target_files,
        Path(request.source_sprite_file),
        Path(request.target_sprite_file),
        in_place=request.in_place,
        overwrite=request.overwrite,
        identity_change_message="Source/Target publication identity changed before Target Commit",
    )
    runtime = services.probe_runtime(request)
    with completion as mutation:
        payload = request.model_dump(
            exclude_none=True,
            exclude={
                "aseprite",
                "timeout_seconds",
                "target_sprite_file",
                "in_place",
                "overwrite",
            },
        )

        def encode_integer_strings(value: object) -> object:
            # Preserve exact integers across Aseprite JSON decoding through doubles.
            if type(value) is int:
                return str(value)
            if isinstance(value, dict):
                return {
                    key: encode_integer_strings(item) for key, item in value.items()
                }
            if isinstance(value, list):
                return [encode_integer_strings(item) for item in value]
            return value

        payload = encode_integer_strings(payload)
        assert isinstance(payload, dict)
        payload.update(
            operation=operation,
            operation_limits=dict(TILE_REGION_LIMITS),
            staged_sprite_file=str(mutation.staged_sprite_file),
        )
        invocation = services.invoke_kernel(
            runtime, TILE_REGION_HANDLER, payload, request.timeout_seconds
        )
        try:
            _reject(invocation, request)
            evidence = TilemapRegionEvidence.model_validate(invocation.payload)
            _validate_evidence(request, evidence)
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Invalid Tilemap region evidence: {exc}",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        return result_type.model_validate(
            {**evidence.model_dump(), "target_commit": mutation.commit().model_dump()}
        )


def set_tilemap(
    request: TilemapSetRequest, services: OperationServices
) -> TilemapSetResult:
    return _mutate(request, services, "set", TilemapSetResult)


def patch_tilemap(
    request: TilemapPatchRequest, services: OperationServices
) -> TilemapPatchResult:
    return _mutate(request, services, "patch", TilemapPatchResult)


def fill_tilemap(
    request: TilemapFillRequest, services: OperationServices
) -> TilemapFillResult:
    return _mutate(request, services, "fill", TilemapFillResult)


TILE_REGION_OPERATIONS = (
    OperationDescriptor(
        "tilemap set",
        TilemapSetRequest,
        TilemapSetResult,
        set_tilemap,
        lambda result: result.target_commit.target_sprite_file,
        TILE_REGION_REQUIREMENTS,
        TILE_REGION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "tilemap patch",
        TilemapPatchRequest,
        TilemapPatchResult,
        patch_tilemap,
        lambda result: result.target_commit.target_sprite_file,
        TILE_REGION_REQUIREMENTS,
        TILE_REGION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "tilemap fill",
        TilemapFillRequest,
        TilemapFillResult,
        fill_tilemap,
        lambda result: result.target_commit.target_sprite_file,
        TILE_REGION_REQUIREMENTS,
        TILE_REGION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
