"""Keyed Tile lifecycle with native record preservation and complete remapping."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.document.sprite import (
    SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteInspection,
)
from spa.authoring.document.targets import (
    LAYER_ADDRESS_FAILURE_CODES,
    LayerTargetDetails,
)
from spa.authoring.raster.image_snapshot import SNAPSHOT_RESOURCE
from spa.authoring.tile.targets import (
    TILE_KEY_RESOURCE,
    TILESET_RESOURCE,
    TileAddress,
    TileInspectionDetails,
    TilesetTarget,
)
from spa.authoring.tile.values import EmptyPlacement, TilemapLayer, TilesetFacts
from spa.contracts.digest import DIGEST_RESOURCE, fnv1a64
from spa.contracts.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    validate_native_sprite_path,
)
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
from spa.contracts.public import (
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.contracts.raster import (
    RASTER_COLOR_RESOURCE,
    EffectivePaletteFact,
    ImageContentDigest,
    PixelRegionSnapshot,
)

TileKey = Annotated[str, Field(min_length=1, pattern=r"^[^\x00]*$")]


class TileMutationRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    target: TilesetTarget

    _paths = field_validator("source_sprite_file", "target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def commit_intent(self) -> "TileMutationRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class TileAddRequest(TileMutationRequest):
    tile_key: TileKey
    image: PixelRegionSnapshot
    palette_frame_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def palette_basis(self) -> "TileAddRequest":
        if (self.image.color_mode == "indexed") != (
            self.palette_frame_number is not None
        ):
            raise ValueError(
                "Only Indexed Tile input requires an explicit Palette Frame"
            )
        return self


class TileIdentity(PublicModel):
    tile_index: int = Field(ge=0)
    tile_key: str | None


class TileAssignKeyRequest(TileMutationRequest):
    tile_index: int = Field(ge=1)
    tile_key: TileKey


class TileIndexMapping(PublicModel):
    old_index: int = Field(ge=0)
    new_index: int = Field(ge=0)
    tile_key: str | None


class KeyedReplacement(PublicModel):
    kind: Literal["tile"] = "tile"
    tile_key: TileKey


TileReplacement = Annotated[
    EmptyPlacement | KeyedReplacement, Field(discriminator="kind")
]


class TileRemoveRequest(TileMutationRequest):
    tile_key: TileKey
    replacement: TileReplacement | None = None


class TileReorderRequest(TileMutationRequest):
    tile_keys: list[TileKey]

    @field_validator("tile_keys")
    @classmethod
    def unique_keys(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Reorder must contain each Tile Key exactly once")
        return value


class AffectedTilemapCel(PublicModel):
    layer: TilemapLayer
    frame_number: int = Field(ge=1)
    changed_cells: int = Field(gt=0)


class TileLifecycleEvidence(PublicModel):
    before_tileset: TilesetFacts
    tileset: TilesetFacts
    before_tiles: list[TileIdentity]
    tiles: list[TileIdentity]
    index_mapping: list[TileIndexMapping]
    tile: TileIdentity | None
    removed_tile: TileIdentity | None
    replacement: TileReplacement | None
    effective_palette: EffectivePaletteFact | None
    transparent_index: int | None = Field(ge=0, le=255)
    image_content_digest: ImageContentDigest | None
    affected_layers: list[TilemapLayer]
    affected_cels: list[AffectedTilemapCel]
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]


class TileAddResult(TileLifecycleEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset tile add"] = "spa tileset tile add"
    target_commit: TargetCommit


class TileAssignKeyResult(TileLifecycleEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset tile assign-key"] = "spa tileset tile assign-key"
    target_commit: TargetCommit


class TileRemoveResult(TileLifecycleEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset tile remove"] = "spa tileset tile remove"
    target_commit: TargetCommit


class TileReorderResult(TileLifecycleEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset tile reorder"] = "spa tileset tile reorder"
    target_commit: TargetCommit


class TileLifecycleDetails(PublicModel):
    kind: Literal["tile_lifecycle"] = "tile_lifecycle"
    target: TilesetTarget
    reason: Literal[
        "key_conflict",
        "already_keyed",
        "invalid_permutation",
        "image_incompatible",
        "palette_frame",
        "palette_index",
        "replacement_required",
        "replacement_invalid",
        "invalid_placement",
    ]
    message: str


TILE_LIFECYCLE_FAILURE_SPECS = (
    FailureCodeSpec(
        "tile_lifecycle_invalid",
        "The requested Tile lifecycle change cannot preserve Tile meaning",
        "input",
        TileLifecycleDetails,
    ),
)
TILE_LIFECYCLE_PROBE_RESOURCE = PackagedResource(
    "tile_lifecycle_probe", "tile/lifecycle_probe.lua"
)
TILE_MUTATE_HANDLER = PackagedHandler(
    "tile_mutate",
    "tile/mutate.lua",
    (
        *SPRITE_INSPECTION_RESOURCES,
        SPRITE_PERSISTENCE_RESOURCE,
        DIGEST_RESOURCE,
        TILESET_RESOURCE,
        TILE_KEY_RESOURCE,
        PackagedResource("tile_lifecycle", "tile/lifecycle.lua"),
        PackagedResource("tile_properties", "tile/properties.lua"),
        SNAPSHOT_RESOURCE,
        RASTER_COLOR_RESOURCE,
        EFFECTIVE_PALETTE_RESOURCE,
    ),
)
TILE_LIFECYCLE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_sprite_inspection",
        "aseprite_tile_inspection",
        "aseprite_tile_lifecycle",
    ],
)
_TILE_TARGET_FAILURE_CODES = (
    "tileset_missing",
    "tileset_ambiguous",
    "tilemap_layer_required",
    "tile_key_missing",
    "tile_key_ambiguous",
    "tile_index_out_of_bounds",
)
TILE_MUTATION_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    *LAYER_ADDRESS_FAILURE_CODES,
    *_TILE_TARGET_FAILURE_CODES,
    "tile_lifecycle_invalid",
    "target_commit_failed",
)


def _reject(invocation: KernelInvocationResult, request: TileMutationRequest) -> None:
    rejected = invocation.payload.get("rejection")
    if rejected is None:
        return
    if not isinstance(rejected, dict):
        raise TypeError("Invalid Tile rejection")
    code = rejected.get("code")
    if code == "tile_lifecycle_invalid":
        # Address numbers cross JSON/Lua as decimal strings, never rounded doubles.
        details = TileLifecycleDetails.model_validate(
            {**rejected.get("details", {}), "target": request.target.model_dump()}
        )
        raise OperationIssue(code, details.message, details)
    if not isinstance(rejected.get("message"), str):
        raise TypeError("Tile rejection lacks a message")
    if code in LAYER_ADDRESS_FAILURE_CODES and request.target.layer is not None:
        raise OperationIssue(
            code,
            rejected["message"],
            LayerTargetDetails(address_role="target", address=request.target.layer),
        )
    if code not in _TILE_TARGET_FAILURE_CODES:
        raise ValueError("Unknown Tile lifecycle rejection")
    tile = (
        TileAddress(tile_index=request.tile_index)
        if isinstance(request, TileAssignKeyRequest)
        else TileAddress(tile_key=request.tile_key)
        if isinstance(request, (TileAddRequest, TileRemoveRequest))
        else None
    )
    raise OperationIssue(
        code,
        rejected["message"],
        TileInspectionDetails(target=request.target, tile=tile),
    )


def _image_bytes(image: PixelRegionSnapshot) -> bytes:
    rows = []
    for row in image.rows:
        for run in row:
            color = run.color
            if color.kind == "rgba":
                pixel = bytes((color.red, color.green, color.blue, color.alpha))
            elif color.kind == "grayscale":
                pixel = bytes((color.gray, color.alpha))
            else:
                pixel = bytes((color.index,))
            rows.append(pixel * run.length)
    area = image.rectangle
    bpp = {"rgb": 4, "grayscale": 2, "indexed": 1}[image.color_mode]
    header = f"{image.color_mode}:{area.width}x{area.height}:{bpp}:{area.width * bpp}:"
    return header.encode() + b"".join(rows)


def _validate_evidence(
    request: TileMutationRequest, evidence: TileLifecycleEvidence
) -> None:
    before, after = evidence.before_tileset, evidence.tileset
    persisted = evidence.sprite.tilesets
    if (
        persisted is None
        or after.tileset_index > len(persisted)
        or len(persisted) != evidence.sprite.metadata.tileset_count
    ):
        raise ValueError("Incomplete persisted Tileset inspection")
    selected = persisted[after.tileset_index - 1]
    if (
        selected.tile_count != after.tile_count
        or selected.name != after.name
        or selected.base_index != after.base_index
        or selected.grid_origin != after.grid.origin
        or selected.tile_size != after.grid.tile_size
    ):
        raise ValueError("Tileset facts disagree with persisted Sprite inspection")
    for facts, tiles in ((before, evidence.before_tiles), (after, evidence.tiles)):
        if [tile.tile_index for tile in tiles] != list(
            range(facts.tile_count)
        ) or tiles[0].tile_key is not None:
            raise ValueError("Incomplete Tile order")
    target = request.target
    if (
        target.tileset_index is not None
        and before.tileset_index != target.tileset_index
    ) or (target.tileset_name is not None and before.name != target.tileset_name):
        raise ValueError("Tileset evidence differs from the request")
    if target.layer is not None:
        layer = target.layer
        if not any(
            (layer.layer_path is None or layer.layer_path == fact.layer_path)
            and (layer.layer_uuid is None or layer.layer_uuid == fact.layer_uuid)
            and (layer.layer_name is None or layer.layer_name == fact.name)
            for fact in before.layers
        ):
            raise ValueError("Requested Layer does not bind the observed Tileset")
    if before.model_dump(exclude={"tile_count", "layers"}) != after.model_dump(
        exclude={"tile_count", "layers"}
    ) or len(before.layers) != len(after.layers):
        raise ValueError("Tile lifecycle changed Tileset identity or bindings")
    for old, new in zip(before.layers, after.layers, strict=True):
        if old.model_dump(exclude={"layer_uuid"}) != new.model_dump(
            exclude={"layer_uuid"}
        ) or (old.layer_uuid is not None and old.layer_uuid != new.layer_uuid):
            raise ValueError("Tile lifecycle changed a Layer binding")
    if isinstance(request, TileAddRequest):
        created = TileIdentity(tile_index=before.tile_count, tile_key=request.tile_key)
        expected = [*evidence.before_tiles, created]
        if (
            any(tile.tile_key == request.tile_key for tile in evidence.before_tiles)
            or evidence.tile != created
            or evidence.removed_tile is not None
            or evidence.replacement is not None
            or evidence.affected_cels
            or evidence.affected_layers
        ):
            raise ValueError("Add evidence differs from append intent")
        mappings = [
            TileIndexMapping(
                old_index=tile.tile_index,
                new_index=tile.tile_index,
                tile_key=tile.tile_key,
            )
            for tile in evidence.before_tiles
        ]
        if evidence.image_content_digest != ImageContentDigest(
            value=fnv1a64(_image_bytes(request.image))
        ):
            raise ValueError("Appended Image differs from the input Snapshot")
        size = after.grid.tile_size
        if (
            request.image.rectangle.width != size.width
            or request.image.rectangle.height != size.height
            or request.image.color_mode != evidence.sprite.metadata.color_mode
        ):
            raise ValueError(
                "Appended Image differs from the Tileset Grid or Sprite Color Mode"
            )
        palette = evidence.effective_palette
        if request.image.color_mode == "indexed":
            used = sorted(
                {
                    run.color.index
                    for row in request.image.rows
                    for run in row
                    if run.color.kind == "palette-index"
                }
            )
            if (
                palette is None
                or evidence.transparent_index is None
                or evidence.transparent_index
                != evidence.sprite.metadata.transparent_color_index
                or palette.frame_number != request.palette_frame_number
                or palette.palette_frame_number > palette.frame_number
                or evidence.transparent_index >= palette.palette_size
                or [item.index for item in palette.indexes] != used
                or any(index >= palette.palette_size for index in used)
            ):
                raise ValueError(
                    "Indexed add lacks its complete requested Palette basis"
                )
            changes = [
                change
                for change in evidence.sprite.palettes or []
                if change.frame_number <= palette.frame_number
            ]
            if (
                not changes
                or palette.frame_number > evidence.sprite.metadata.frame_count
            ):
                raise ValueError("Palette basis is outside persisted Frame coverage")
            resolved = max(changes, key=lambda change: change.frame_number)
            if (
                resolved.frame_number != palette.palette_frame_number
                or len(resolved.entries) != palette.palette_size
                or any(
                    item.color != resolved.entries[item.index].color
                    for item in palette.indexes
                )
            ):
                raise ValueError(
                    "Used index colors disagree with the persisted Effective Palette"
                )
        elif palette is not None or evidence.transparent_index is not None:
            raise ValueError("Non-Indexed add has inapplicable Palette evidence")
        if evidence.tiles != expected or evidence.index_mapping != mappings:
            raise ValueError("Append changed existing Tile order or mapping")
    elif isinstance(request, TileAssignKeyRequest):
        selected = request.tile_index
        if (
            selected >= len(evidence.before_tiles)
            or evidence.before_tiles[selected].tile_key is not None
            or any(tile.tile_key == request.tile_key for tile in evidence.before_tiles)
        ):
            raise ValueError("Assignment requires an unkeyed Tile and a unique new Key")
        expected = list(evidence.before_tiles)
        expected[selected] = TileIdentity(
            tile_index=selected, tile_key=request.tile_key
        )
        mappings = [
            TileIndexMapping(
                old_index=tile.tile_index,
                new_index=tile.tile_index,
                tile_key=tile.tile_key,
            )
            for tile in evidence.before_tiles
        ]
        if (
            evidence.tile != expected[selected]
            or evidence.tiles != expected
            or evidence.index_mapping != mappings
            or evidence.removed_tile is not None
            or evidence.replacement is not None
            or evidence.image_content_digest is not None
            or evidence.effective_palette is not None
            or evidence.transparent_index is not None
            or evidence.affected_layers
            or evidence.affected_cels
        ):
            raise ValueError("Missing Key assignment changed unrelated facts")
    elif isinstance(request, TileRemoveRequest):
        matched = [
            tile
            for tile in evidence.before_tiles[1:]
            if tile.tile_key == request.tile_key
        ]
        if (
            len(matched) != 1
            or evidence.removed_tile != matched[0]
            or evidence.replacement != request.replacement
        ):
            raise ValueError("Removed Tile or replacement differs from request")
        removed = matched[0].tile_index
        remaining = [
            tile for tile in evidence.before_tiles if tile.tile_index != removed
        ]
        expected = [
            TileIdentity(tile_index=index, tile_key=tile.tile_key)
            for index, tile in enumerate(remaining)
        ]
        replacement = 0
        if isinstance(request.replacement, KeyedReplacement):
            candidates = [
                tile
                for tile in expected[1:]
                if tile.tile_key == request.replacement.tile_key
            ]
            if len(candidates) != 1:
                raise ValueError(
                    "Replacement Key is not unique in the remaining Tileset"
                )
            replacement = candidates[0].tile_index
        mappings = [
            TileIndexMapping(
                old_index=tile.tile_index,
                new_index=replacement
                if tile.tile_index == removed
                else tile.tile_index - int(tile.tile_index > removed),
                tile_key=tile.tile_key,
            )
            for tile in evidence.before_tiles
        ]
        _validate_remap(evidence, expected, mappings)
    elif isinstance(request, TileReorderRequest):
        keys = [tile.tile_key for tile in evidence.before_tiles[1:]]
        if (
            None in keys
            or len(keys) != len(set(keys))
            or set(keys) != set(request.tile_keys)
            or evidence.removed_tile is not None
            or evidence.replacement is not None
        ):
            raise ValueError("Reorder requires every current unique Tile Key")
        expected = [
            TileIdentity(tile_index=0, tile_key=None),
            *[
                TileIdentity(tile_index=index, tile_key=key)
                for index, key in enumerate(request.tile_keys, 1)
            ],
        ]
        destinations = {tile.tile_key: tile.tile_index for tile in expected}
        mappings = [
            TileIndexMapping(
                old_index=tile.tile_index,
                new_index=destinations[tile.tile_key],
                tile_key=tile.tile_key,
            )
            for tile in evidence.before_tiles
        ]
        _validate_remap(evidence, expected, mappings)


def _validate_remap(
    evidence: TileLifecycleEvidence,
    expected: list[TileIdentity],
    mappings: list[TileIndexMapping],
) -> None:
    if (
        evidence.tile is not None
        or evidence.tiles != expected
        or evidence.index_mapping != mappings
        or evidence.image_content_digest is not None
        or evidence.effective_palette is not None
        or evidence.transparent_index is not None
    ):
        raise ValueError("Complete Tile order or mapping differs from request")
    cels = evidence.sprite.cels or []
    seen = set()
    paths = set()
    for affected in evidence.affected_cels:
        address = (tuple(affected.layer.layer_path), affected.frame_number)
        if address in seen or affected.layer not in evidence.tileset.layers:
            raise ValueError("Duplicate or unrelated affected Cel")
        actual = [
            cel for cel in cels if (tuple(cel.layer_path), cel.frame_number) == address
        ]
        if (
            len(actual) != 1
            or affected.changed_cells > actual[0].bounds.width * actual[0].bounds.height
        ):
            raise ValueError("Affected Cell count exceeds a persisted Cel")
        seen.add(address)
        paths.add(address[0])
    if (
        len(evidence.affected_layers) != len(paths)
        or {tuple(layer.layer_path) for layer in evidence.affected_layers} != paths
        or any(
            layer not in evidence.tileset.layers for layer in evidence.affected_layers
        )
    ):
        raise ValueError("Affected Layers disagree with affected Cels")


def _mutate[T: TileLifecycleEvidence](
    request: TileMutationRequest,
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
            exclude={
                "aseprite",
                "timeout_seconds",
                "target_sprite_file",
                "in_place",
                "overwrite",
            },
            exclude_none=True,
        )

        def addresses(value: object) -> object:
            if type(value) is int:
                return str(value)
            if isinstance(value, dict):
                return {key: addresses(item) for key, item in value.items()}
            if isinstance(value, list):
                return [addresses(item) for item in value]
            return value

        payload["target"] = addresses(payload["target"])
        for field in ("tile_index", "palette_frame_number"):
            if field in payload:
                payload[field] = str(payload[field])
        payload.update(
            operation=operation, staged_sprite_file=str(mutation.staged_sprite_file)
        )
        invocation = services.invoke_kernel(
            runtime, TILE_MUTATE_HANDLER, payload, request.timeout_seconds
        )
        try:
            _reject(invocation, request)
            evidence = TileLifecycleEvidence.model_validate(invocation.payload)
            _validate_evidence(request, evidence)
        except (ValueError, TypeError, IndexError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Invalid Tile lifecycle evidence: {exc}",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        return result_type.model_validate(
            {**evidence.model_dump(), "target_commit": mutation.commit().model_dump()}
        )


def add_tile(request: TileAddRequest, services: OperationServices) -> TileAddResult:
    return _mutate(request, services, "add", TileAddResult)


def assign_tile_key(
    request: TileAssignKeyRequest, services: OperationServices
) -> TileAssignKeyResult:
    return _mutate(request, services, "assign-key", TileAssignKeyResult)


def remove_tile(
    request: TileRemoveRequest, services: OperationServices
) -> TileRemoveResult:
    return _mutate(request, services, "remove", TileRemoveResult)


def reorder_tiles(
    request: TileReorderRequest, services: OperationServices
) -> TileReorderResult:
    return _mutate(request, services, "reorder", TileReorderResult)


TILE_LIFECYCLE_OPERATIONS = (
    OperationDescriptor(
        "tileset tile add",
        TileAddRequest,
        TileAddResult,
        add_tile,
        lambda result: result.target_commit.target_sprite_file,
        TILE_LIFECYCLE_REQUIREMENTS,
        TILE_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "tileset tile assign-key",
        TileAssignKeyRequest,
        TileAssignKeyResult,
        assign_tile_key,
        lambda result: result.target_commit.target_sprite_file,
        TILE_LIFECYCLE_REQUIREMENTS,
        TILE_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "tileset tile remove",
        TileRemoveRequest,
        TileRemoveResult,
        remove_tile,
        lambda result: result.target_commit.target_sprite_file,
        TILE_LIFECYCLE_REQUIREMENTS,
        TILE_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "tileset tile reorder",
        TileReorderRequest,
        TileReorderResult,
        reorder_tiles,
        lambda result: result.target_commit.target_sprite_file,
        TILE_LIFECYCLE_REQUIREMENTS,
        TILE_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
