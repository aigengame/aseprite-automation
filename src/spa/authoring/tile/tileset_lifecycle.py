"""Explicit Tileset removal and keyed Layer rebinding, standalone or in a Plan."""

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
    LayerAddress,
    LayerTargetDetails,
)
from spa.authoring.tile.lifecycle import TileKey, TileReplacement
from spa.authoring.tile.targets import (
    TILE_KEY_RESOURCE,
    TILESET_RESOURCE,
    TileInspectionDetails,
    TilesetTarget,
)
from spa.authoring.tile.values import TilemapLayer, TilesetFacts
from spa.contracts.digest import DIGEST_RESOURCE
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
    Point,
    PositiveRectangle,
    Size,
)


class TilesetRemoveInput(PublicModel):
    target: TilesetTarget


class MapByKey(PublicModel):
    kind: Literal["by_key"]


class TileKeyMapping(PublicModel):
    source_key: TileKey
    target: TileReplacement


class ExplicitTileMapping(PublicModel):
    kind: Literal["explicit"]
    entries: list[TileKeyMapping]

    @model_validator(mode="after")
    def unique_sources(self) -> "ExplicitTileMapping":
        keys = [entry.source_key for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("Explicit mapping must contain each source Tile Key once")
        return self


class TilesetRebindInput(PublicModel):
    layer: LayerAddress
    target: TilesetTarget
    mapping: Annotated[MapByKey | ExplicitTileMapping, Field(discriminator="kind")]
    grid_policy: Literal["require_equal", "use_target"]


class TilesetMutationRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool

    _paths = field_validator("source_sprite_file", "target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def commit_intent(self) -> "TilesetMutationRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class TilesetRemoveRequest(TilesetMutationRequest, TilesetRemoveInput):
    pass


class TilesetRebindRequest(TilesetMutationRequest, TilesetRebindInput):
    pass


class TilesetIndexMapping(PublicModel):
    old_index: int = Field(ge=1)
    new_index: int | None = Field(ge=1)


class TilesetCollectionEvidence(PublicModel):
    before_tilesets: list[TilesetFacts]
    tilesets: list[TilesetFacts]
    unchanged_facts_verified: Literal[True]


class TilesetRemoveEvidence(TilesetCollectionEvidence):
    removed_tileset: TilesetFacts
    index_mapping: list[TilesetIndexMapping]


class ReboundTile(PublicModel):
    source_tile_key: TileKey
    source_index: int = Field(ge=1)
    target_tile_key: TileKey | None
    target_index: int = Field(ge=0)

    @model_validator(mode="after")
    def empty_has_no_key(self) -> "ReboundTile":
        if (self.target_index == 0) != (self.target_tile_key is None):
            raise ValueError("Only Empty Tile 0 has no target Tile Key")
        return self


class ReboundCel(PublicModel):
    frame_number: int = Field(ge=1)
    position: Point
    cell_size: Size
    before_coverage: PositiveRectangle
    canvas_coverage: PositiveRectangle
    changed_cells: int = Field(ge=0)
    used_source_indexes: list[int]
    used_target_indexes: list[int]


class UsagePaletteCheck(PublicModel):
    frame_number: int = Field(ge=1)
    tile_indexes: list[int]
    effective_palette: EffectivePaletteFact


class TilesetRebindEvidence(TilesetCollectionEvidence):
    layer: TilemapLayer
    before_tileset: TilesetFacts
    tileset: TilesetFacts
    tile_mapping: list[ReboundTile]
    cels: list[ReboundCel]
    palette_checks: list[UsagePaletteCheck]
    transparent_index: int | None = Field(ge=0, le=255)


class TilesetRemoveResult(TilesetRemoveEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset remove"] = "spa tileset remove"
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]
    target_commit: TargetCommit


class TilesetRebindResult(TilesetRebindEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa layer set-tileset"] = "spa layer set-tileset"
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]
    target_commit: TargetCommit


class TilesetInUseDetails(PublicModel):
    step_number: int | None = Field(default=None, ge=1)
    kind: Literal["tileset_in_use"] = "tileset_in_use"
    target: TilesetTarget
    tileset: TilesetFacts
    layers: list[TilemapLayer] = Field(min_length=1)


class TilesetLifecycleDetails(PublicModel):
    step_number: int | None = Field(default=None, ge=1)
    kind: Literal["tileset_lifecycle"] = "tileset_lifecycle"
    target: TilesetTarget
    layer: LayerAddress | None = None
    reason: Literal[
        "grid_mismatch",
        "mapping_incomplete",
        "mapping_invalid",
        "palette_index",
        "invalid_placement",
    ]
    message: str
    frame_number: int | None = Field(default=None, ge=1)
    tile_index: int | None = Field(default=None, ge=0)


TILESET_FAILURE_SPECS = (
    FailureCodeSpec(
        "tileset_in_use",
        "Every Tilemap Layer reference must be resolved before removal",
        "input",
        TilesetInUseDetails,
    ),
    FailureCodeSpec(
        "tileset_lifecycle_invalid",
        "The requested Tileset change cannot preserve the declared Tile meaning",
        "input",
        TilesetLifecycleDetails,
    ),
)
TILESET_LIFECYCLE_RESOURCE = PackagedResource(
    "tileset_lifecycle", "tile/tileset_lifecycle.lua"
)
TILESET_LIFECYCLE_PROBE_RESOURCE = PackagedResource(
    "tileset_lifecycle_probe", "tile/tileset_lifecycle_probe.lua"
)
TILESET_LIFECYCLE_RESOURCES = (
    *SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    DIGEST_RESOURCE,
    TILESET_RESOURCE,
    TILE_KEY_RESOURCE,
    TILESET_LIFECYCLE_RESOURCE,
    PackagedResource("tile_properties", "tile/properties.lua"),
    RASTER_COLOR_RESOURCE,
    EFFECTIVE_PALETTE_RESOURCE,
)
TILESET_MUTATE_HANDLER = PackagedHandler(
    "tileset_mutate", "tile/tileset_mutate.lua", TILESET_LIFECYCLE_RESOURCES
)
TILESET_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_sprite_inspection",
        "aseprite_tile_inspection",
        "aseprite_tileset_lifecycle",
    ],
)
_TILESET_TARGET_CODES = (
    "tileset_missing",
    "tileset_ambiguous",
    "tilemap_layer_required",
    "tile_key_missing",
    "tile_key_ambiguous",
    "tile_index_out_of_bounds",
)
TILESET_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    *LAYER_ADDRESS_FAILURE_CODES,
    *_TILESET_TARGET_CODES,
    "tileset_in_use",
    "tileset_lifecycle_invalid",
    "target_commit_failed",
)


def tileset_payload(input: TilesetRemoveInput | TilesetRebindInput) -> dict:
    """Addresses cross JSON/Lua as decimal strings, without double rounding."""

    def addresses(value: object) -> object:
        if type(value) is int:
            return str(value)
        if isinstance(value, dict):
            return {key: addresses(item) for key, item in value.items()}
        if isinstance(value, list):
            return [addresses(item) for item in value]
        return value

    value = input.model_dump(
        include={"target", "layer", "mapping", "grid_policy"}, exclude_none=True
    )
    value["target"] = addresses(value["target"])
    if "layer" in value:
        value["layer"] = addresses(value["layer"])
    return value


def reject_tileset(
    input: TilesetRemoveInput | TilesetRebindInput, invocation: KernelInvocationResult
) -> None:
    rejected = invocation.payload.get("rejection")
    if rejected is None:
        return
    if not isinstance(rejected, dict) or not isinstance(rejected.get("message"), str):
        raise TypeError("Invalid Tileset rejection")
    code, message = rejected.get("code"), rejected["message"]
    if code == "tileset_in_use":
        details = TilesetInUseDetails.model_validate(
            {**rejected.get("details", {}), "target": input.target.model_dump()}
        )
        if details.layers != details.tileset.layers:
            raise ValueError("Tileset refusal lacks complete reference facts")
        raise OperationIssue(code, message, details)
    if code == "tileset_lifecycle_invalid":
        details = TilesetLifecycleDetails.model_validate(
            {
                **rejected.get("details", {}),
                "target": input.target.model_dump(),
                "layer": input.layer.model_dump()
                if isinstance(input, TilesetRebindInput)
                else None,
            }
        )
        raise OperationIssue(code, message, details)
    if code in LAYER_ADDRESS_FAILURE_CODES:
        address = (
            input.layer
            if isinstance(input, TilesetRebindInput)
            and rejected.get("address_role") != "target"
            else input.target.layer
        )
        if address is None:
            raise ValueError("Layer rejection has no requested address")
        raise OperationIssue(
            code, message, LayerTargetDetails(address_role="target", address=address)
        )
    if code not in _TILESET_TARGET_CODES:
        raise ValueError("Unknown Tileset rejection")
    raise OperationIssue(code, message, TileInspectionDetails(target=input.target))


def _matches(target: TilesetTarget, facts: TilesetFacts) -> bool:
    if target.tileset_index is not None:
        return target.tileset_index == facts.tileset_index
    if target.tileset_name is not None:
        return target.tileset_name == facts.name
    assert target.layer is not None
    return any(_layer_matches(target.layer, layer) for layer in facts.layers)


def _layer_matches(address: LayerAddress, facts: TilemapLayer) -> bool:
    return (
        (address.layer_path is None or address.layer_path == facts.layer_path)
        and (address.layer_uuid is None or address.layer_uuid == facts.layer_uuid)
        and (address.layer_name is None or address.layer_name == facts.name)
    )


def validate_tileset_evidence(
    input: TilesetRemoveInput | TilesetRebindInput,
    evidence: TilesetRemoveEvidence | TilesetRebindEvidence,
) -> None:
    for items in (evidence.before_tilesets, evidence.tilesets):
        if [item.tileset_index for item in items] != list(range(1, len(items) + 1)):
            raise ValueError("Tileset collection evidence is incomplete")
    if isinstance(input, TilesetRemoveInput):
        if not isinstance(evidence, TilesetRemoveEvidence):
            raise TypeError("Remove has incompatible evidence")
        removed = evidence.removed_tileset
        if (
            not _matches(input.target, removed)
            or removed.layers
            or removed not in evidence.before_tilesets
        ):
            raise ValueError("Removal did not target an unreferenced Tileset")
        expected, mapping = [], []
        for before in evidence.before_tilesets:
            new_index = None
            if before.tileset_index != removed.tileset_index:
                new_index = len(expected) + 1
                expected.append(before.model_copy(update={"tileset_index": new_index}))
            mapping.append(
                TilesetIndexMapping(old_index=before.tileset_index, new_index=new_index)
            )
        if expected != evidence.tilesets or mapping != evidence.index_mapping:
            raise ValueError("Removal changed unrelated Tileset or Layer facts")
        return
    if not isinstance(evidence, TilesetRebindEvidence):
        raise TypeError("Rebind has incompatible evidence")
    if not _layer_matches(input.layer, evidence.layer) or not _matches(
        input.target, evidence.tileset
    ):
        raise ValueError("Rebind target differs from request")
    if (
        evidence.before_tileset not in evidence.before_tilesets
        or evidence.layer not in evidence.before_tileset.layers
        or evidence.tileset not in evidence.tilesets
        or evidence.layer not in evidence.tileset.layers
    ):
        raise ValueError("Rebind lacks old and new Layer bindings")
    if (
        input.grid_policy == "require_equal"
        and evidence.before_tileset.grid != evidence.tileset.grid
    ):
        raise ValueError("Rebind violated equal Grid policy")
    before = {item.tileset_index: item for item in evidence.before_tilesets}
    for after in evidence.tilesets:
        if after.tileset_index not in before or after.model_dump(
            exclude={"layers"}
        ) != before[after.tileset_index].model_dump(exclude={"layers"}):
            raise ValueError("Rebind changed Tileset structure")
        expected_layers = [
            layer
            for layer in before[after.tileset_index].layers
            if layer != evidence.layer
        ]
        if after.tileset_index == evidence.tileset.tileset_index:
            expected_layers.append(evidence.layer)
        if sorted(expected_layers, key=lambda layer: layer.layer_path) != sorted(
            after.layers, key=lambda layer: layer.layer_path
        ):
            raise ValueError("Rebind changed another Layer reference")
    if len(before) != len(evidence.tilesets):
        raise ValueError("Rebind changed Tileset count")
    mappings = evidence.tile_mapping
    if len({item.source_tile_key for item in mappings}) != len(mappings) or len(
        {item.source_index for item in mappings}
    ) != len(mappings):
        raise ValueError("Rebind mapping duplicates a used source Tile")
    if input.mapping.kind == "by_key":
        if any(item.source_tile_key != item.target_tile_key for item in mappings):
            raise ValueError("Rebind did not preserve Tile Keys")
    else:
        requested = {
            entry.source_key: (
                None if entry.target.kind == "empty" else entry.target.tile_key
            )
            for entry in input.mapping.entries
        }
        if {
            item.source_tile_key: item.target_tile_key for item in mappings
        } != requested:
            raise ValueError("Rebind differs from its complete explicit mapping")
    frames = [cel.frame_number for cel in evidence.cels]
    if len(frames) != len(set(frames)):
        raise ValueError("Rebind reports duplicate logical Cels")
    mapped = {item.source_index: item.target_index for item in mappings}
    changed_tileset = (
        evidence.before_tileset.tileset_index != evidence.tileset.tileset_index
    )
    required = {}
    for cel in evidence.cels:
        for grid, area in (
            (evidence.before_tileset.grid, cel.before_coverage),
            (evidence.tileset.grid, cel.canvas_coverage),
        ):
            if area != PositiveRectangle(
                x=cel.position.x,
                y=cel.position.y,
                width=cel.cell_size.width * grid.tile_size.width,
                height=cel.cell_size.height * grid.tile_size.height,
            ):
                raise ValueError("Rebind coverage differs from the preserved Cell grid")
        if (
            cel.changed_cells > cel.cell_size.width * cel.cell_size.height
            or cel.used_source_indexes != sorted(set(cel.used_source_indexes))
            or not set(cel.used_source_indexes) <= mapped.keys()
        ):
            raise ValueError("Rebind has invalid affected Cell facts")
        if cel.used_target_indexes != sorted(
            {mapped[index] for index in cel.used_source_indexes if mapped[index] != 0}
        ):
            raise ValueError("Rebind target usage differs from its Tile mapping")
        changed = sorted(
            {
                mapped[index]
                for index in cel.used_source_indexes
                if mapped[index] != 0 and (changed_tileset or mapped[index] != index)
            }
        )
        if changed:
            required[cel.frame_number] = changed
    checks = evidence.palette_checks
    if evidence.transparent_index is None:
        if checks:
            raise ValueError("Non-Indexed rebind reports Palette checks")
    else:
        if (
            len(checks) != len(required)
            or {check.frame_number: check.tile_indexes for check in checks} != required
        ):
            raise ValueError("Indexed rebind lacks usage-Frame Palette coverage")
        for check in checks:
            palette = check.effective_palette
            if (
                palette.frame_number != check.frame_number
                or palette.palette_frame_number > check.frame_number
                or evidence.transparent_index >= palette.palette_size
                or any(item.index >= palette.palette_size for item in palette.indexes)
            ):
                raise ValueError(
                    "Indexed rebind has an invalid Effective Palette basis"
                )


def _mutate(
    request: TilesetRemoveRequest | TilesetRebindRequest, services: OperationServices
) -> TilesetRemoveResult | TilesetRebindResult:
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
        removing = isinstance(request, TilesetRemoveRequest)
        payload = tileset_payload(request)
        payload.update(
            operation="remove" if removing else "rebind",
            source_sprite_file=request.source_sprite_file,
            staged_sprite_file=str(mutation.staged_sprite_file),
        )
        invocation = services.invoke_kernel(
            runtime, TILESET_MUTATE_HANDLER, payload, request.timeout_seconds
        )
        try:
            reject_tileset(request, invocation)
            value = dict(invocation.payload)
            sprite = SpriteInspection.model_validate(value.pop("sprite"))
            if value.pop("persisted_reopen_verified") is not True:
                raise ValueError("Tileset mutation lacks persisted evidence")
            evidence = (
                TilesetRemoveEvidence if removing else TilesetRebindEvidence
            ).model_validate(value)
            validate_tileset_evidence(request, evidence)
            if (
                sprite.tilesets is None
                or len(sprite.tilesets) != len(evidence.tilesets)
                or sprite.metadata.tileset_count != len(evidence.tilesets)
            ):
                raise ValueError("Persisted Tileset count differs")
            for actual, fact in zip(sprite.tilesets, evidence.tilesets, strict=True):
                if (
                    actual.name,
                    actual.base_index,
                    actual.tile_count,
                    actual.grid_origin,
                    actual.tile_size,
                ) != (
                    fact.name,
                    fact.base_index,
                    fact.tile_count,
                    fact.grid.origin,
                    fact.grid.tile_size,
                ):
                    raise ValueError("Persisted Tileset structure differs")
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Invalid Tileset lifecycle evidence: {exc}",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        result_type = TilesetRemoveResult if removing else TilesetRebindResult
        return result_type.model_validate(
            {
                **evidence.model_dump(),
                "sprite": sprite.model_dump(),
                "persisted_reopen_verified": True,
                "target_commit": mutation.commit().model_dump(),
            }
        )


def remove_tileset(
    request: TilesetRemoveRequest, services: OperationServices
) -> TilesetRemoveResult:
    result = _mutate(request, services)
    assert isinstance(result, TilesetRemoveResult)
    return result


def rebind_tileset(
    request: TilesetRebindRequest, services: OperationServices
) -> TilesetRebindResult:
    result = _mutate(request, services)
    assert isinstance(result, TilesetRebindResult)
    return result


TILESET_LIFECYCLE_OPERATIONS = (
    OperationDescriptor(
        "tileset remove",
        TilesetRemoveRequest,
        TilesetRemoveResult,
        remove_tileset,
        lambda result: result.target_commit.target_sprite_file,
        TILESET_REQUIREMENTS,
        TILESET_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        plan_eligible=True,
    ),
    OperationDescriptor(
        "layer set-tileset",
        TilesetRebindRequest,
        TilesetRebindResult,
        rebind_tileset,
        lambda result: result.target_commit.target_sprite_file,
        TILESET_REQUIREMENTS,
        TILESET_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        plan_eligible=True,
    ),
)
