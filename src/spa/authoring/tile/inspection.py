"""Read-only Tile Authoring operations over one native Sprite snapshot."""

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.document.cel import CelAddress
from spa.authoring.document.layer import (
    LAYER_FAILURE_CODE_SPECS,
    LayerAddress,
    LayerTargetDetails,
)
from spa.authoring.document.sprite import SPRITE_INSPECTION_RESOURCES
from spa.authoring.raster.image_snapshot import SNAPSHOT_RESOURCE
from spa.authoring.tile.properties import selected_namespaces
from spa.authoring.tile.values import (
    TileFacts,
    TileFinding,
    TilemapFacts,
    TileRegionSnapshot,
    TilesetFacts,
)
from spa.contracts.mutation import validate_native_sprite_path
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
    PixelRegionSnapshot,
    PositiveRectangle,
)
from spa.contracts.snapshot import SnapshotDestination

INLINE_TILE_CELLS = 4096
INLINE_TILE_PIXELS = 4096
TILE_PROBE_RESOURCE = PackagedResource("tile_probe", "tile/probe.lua")
TILE_INSPECTION_RESOURCE = PackagedResource("tile_inspection", "tile/inspection.lua")
TILE_READ_HANDLER = PackagedHandler(
    "tile_read",
    "tile/read.lua",
    (
        *SPRITE_INSPECTION_RESOURCES,
        TILE_INSPECTION_RESOURCE,
        PackagedResource("tile_properties", "tile/properties.lua"),
        SNAPSHOT_RESOURCE,
        RASTER_COLOR_RESOURCE,
        EFFECTIVE_PALETTE_RESOURCE,
    ),
)
TILE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_tile_inspection"],
)


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


class TilesetListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)
    _source = field_validator("sprite_file")(validate_native_sprite_path)


class TilesetTargetRequest(TilesetListRequest):
    target: TilesetTarget


class TilesetGetRequest(TilesetTargetRequest):
    property_namespaces: list[str] = Field(default_factory=list)

    @field_validator("property_namespaces")
    @classmethod
    def native_names(cls, value: list[str]) -> list[str]:
        if any("\x00" in name for name in value):
            raise ValueError("Property namespace names cannot contain NUL")
        return value


class TileGetRequest(TilesetGetRequest):
    tile: TileAddress
    snapshot_destination: SnapshotDestination | None = None


class TilemapGetRequest(TilesetListRequest):
    target: CelAddress
    rectangle: PositiveRectangle | None = None
    snapshot_destination: SnapshotDestination | None = None

    @model_validator(mode="after")
    def declared_region(self) -> "TilemapGetRequest":
        if self.snapshot_destination is not None and self.rectangle is None:
            raise ValueError(
                "A Snapshot destination requires an explicit Tile Cell Rectangle"
            )
        return self


class TilemapValidateRequest(TilesetListRequest):
    target: CelAddress


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


class TilesetListResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset list"] = "spa tileset list"
    sprite_file: str
    complete: Literal[True] = True
    tilesets: list[TilesetFacts]


class TilesetGetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset get"] = "spa tileset get"
    sprite_file: str
    complete: Literal[True] = True
    tileset: TilesetFacts
    tiles: list[TileFacts]

    @model_validator(mode="after")
    def all_tiles(self) -> "TilesetGetResult":
        if [tile.tile_index for tile in self.tiles] != list(
            range(self.tileset.tile_count)
        ):
            raise ValueError("Tileset inspection must include every current Tile index")
        return self


class TileSnapshotArtifact(PublicModel):
    role: Literal["tile-region-snapshot", "pixel-region-snapshot"]
    media_type: Literal["application/json"] = "application/json"
    format: Literal["json"] = "json"
    path: str
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TileGetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset tile get"] = "spa tileset tile get"
    sprite_file: str
    complete: Literal[True] = True
    tileset: TilesetFacts
    tile: TileFacts
    snapshot: PixelRegionSnapshot | None
    output_form: Literal["inline", "artifact"]
    artifact: TileSnapshotArtifact | None = None


class TilemapGetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tilemap get"] = "spa tilemap get"
    sprite_file: str
    complete: Literal[True] = True
    tileset: TilesetFacts
    tilemap: TilemapFacts
    snapshot: TileRegionSnapshot | None
    output_form: Literal["summary", "inline", "artifact"]
    artifact: TileSnapshotArtifact | None = None


class TilemapListResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tilemap list"] = "spa tilemap list"
    sprite_file: str
    complete: Literal[True] = True
    frame_count: int = Field(ge=1)
    tilesets: list[TilesetFacts]
    cels: list[TilemapFacts]


class TilesetValidateResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tileset validate"] = "spa tileset validate"
    sprite_file: str
    complete: Literal[True] = True
    tileset: TilesetFacts
    valid: bool
    findings: list[TileFinding]

    @model_validator(mode="after")
    def verdict(self) -> "TilesetValidateResult":
        if self.valid != (not self.findings):
            raise ValueError("Validation verdict differs from Findings")
        return self


class TilemapValidateResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tilemap validate"] = "spa tilemap validate"
    sprite_file: str
    complete: Literal[True] = True
    tileset: TilesetFacts
    tilemap: TilemapFacts
    valid: bool
    findings: list[TileFinding]

    @model_validator(mode="after")
    def verdict(self) -> "TilemapValidateResult":
        if self.valid != (not self.findings):
            raise ValueError("Validation verdict differs from Findings")
        return self


def _payload(request: TilesetListRequest, operation: str) -> dict:
    value = request.model_dump(
        mode="json",
        exclude={"aseprite", "timeout_seconds", "snapshot_destination"},
        exclude_none=True,
    )

    # Exact unbounded request integers cross the JSON/Lua double boundary as text.
    def integers(item: Any) -> Any:
        if type(item) is int:
            return str(item)
        if isinstance(item, dict):
            return {key: integers(value) for key, value in item.items()}
        if isinstance(item, list):
            return [integers(value) for value in item]
        return item

    value = integers(value)
    if isinstance(request, TilesetGetRequest):
        value["property_namespaces"] = selected_namespaces(request.property_namespaces)
    value.update(
        operation=operation,
        inline_cells=INLINE_TILE_CELLS,
        inline_pixels=INLINE_TILE_PIXELS,
    )
    return value


def _reject(invocation: KernelInvocationResult, request: TilesetListRequest) -> None:
    rejected = invocation.payload.get("rejection")
    if rejected is None:
        return
    if not isinstance(rejected, dict) or not isinstance(rejected.get("message"), str):
        raise TypeError("Invalid Tile rejection")
    code = rejected.get("code")
    target = (
        request.target
        if isinstance(
            request, (TilesetTargetRequest, TilemapGetRequest, TilemapValidateRequest)
        )
        else None
    )
    layer = target.layer if target is not None else None
    if code in {spec.code for spec in LAYER_FAILURE_CODE_SPECS} and layer is not None:
        raise OperationIssue(
            code,
            rejected["message"],
            LayerTargetDetails(address_role="target", address=layer),
        )
    if code not in {spec.code for spec in TILE_FAILURE_SPECS}:
        raise ValueError("Unknown Tile rejection")
    raise OperationIssue(
        code,
        rejected["message"],
        TileInspectionDetails(
            target=target,
            tile=request.tile if isinstance(request, TileGetRequest) else None,
            rectangle=request.rectangle
            if isinstance(request, TilemapGetRequest)
            else None,
            snapshot_limit=TileSnapshotLimit.model_validate(
                rejected.get("snapshot_limit")
            )
            if code == "tile_snapshot_destination_required"
            else None,
        ),
    )


type InspectionResult = (
    TilesetListResult
    | TilesetGetResult
    | TileGetResult
    | TilemapGetResult
    | TilemapListResult
    | TilesetValidateResult
    | TilemapValidateResult
)


def _check_scope(request: TilesetListRequest, result: InspectionResult) -> None:
    if result.sprite_file != request.sprite_file:
        raise ValueError("Tile inspection Source differs from request")
    if isinstance(request, TilesetGetRequest):
        assert isinstance(result, (TilesetGetResult, TileGetResult))
        tiles = result.tiles if isinstance(result, TilesetGetResult) else [result.tile]
        expected = selected_namespaces(request.property_namespaces)
        if any(
            [value.namespace for value in tile.properties] != expected for tile in tiles
        ):
            raise ValueError("Tile property namespaces differ from the selected scope")
    if isinstance(
        request, (TilesetTargetRequest, TilemapGetRequest, TilemapValidateRequest)
    ):
        assert isinstance(
            result,
            (
                TilesetGetResult,
                TileGetResult,
                TilemapGetResult,
                TilesetValidateResult,
                TilemapValidateResult,
            ),
        )
        tileset = result.tileset
        target = request.target
        if isinstance(target, TilesetTarget):
            if (
                target.tileset_index is not None
                and tileset.tileset_index != target.tileset_index
            ):
                raise ValueError("Tileset index differs from request")
            if target.tileset_name is not None and tileset.name != target.tileset_name:
                raise ValueError("Tileset name differs from request")
        else:
            assert isinstance(result, (TilemapGetResult, TilemapValidateResult))
            tilemap = result.tilemap
            if (
                tilemap.frame_number != target.frame_number
                or tilemap.tileset_index != tileset.tileset_index
            ):
                raise ValueError("Tilemap Frame or binding differs from request")
        layer = target.layer
        if layer is not None:
            candidates = (
                tileset.layers
                if isinstance(target, TilesetTarget)
                else [result.tilemap.layer]
                if isinstance(result, (TilemapGetResult, TilemapValidateResult))
                else []
            )
            if not any(
                (layer.layer_path is None or layer.layer_path == item.layer_path)
                and (layer.layer_name is None or layer.layer_name == item.name)
                and (layer.layer_uuid is None or layer.layer_uuid == item.layer_uuid)
                for item in candidates
            ):
                raise ValueError("Tilemap Layer differs from request")
    if isinstance(request, TileGetRequest):
        assert isinstance(result, TileGetResult)
        tile = result.tile
        if (
            request.tile.tile_index is not None
            and tile.tile_index != request.tile.tile_index
        ) or (
            request.tile.tile_key is not None and tile.tile_key != request.tile.tile_key
        ):
            raise ValueError("Tile address differs from request")


def _read[T: InspectionResult](
    request: TilesetListRequest,
    services: OperationServices,
    operation: str,
    result_type: type[T],
) -> T:
    files = services.artifact_files
    export = (
        request.snapshot_destination
        if isinstance(request, (TileGetRequest, TilemapGetRequest))
        else None
    )
    destination, staged = None, None
    if export is not None:
        assert files is not None
        destination = files.normalize_destination(export.path)
        files.ensure_source_separate(Path(request.sprite_file), destination)
        staged = files.staged_path(destination, if_exists=export.if_exists)
    try:
        payload = _payload(request, operation)
        if staged is not None:
            payload["staged_snapshot_file"] = str(staged)
        invocation = services.invoke_kernel(
            services.probe_runtime(request),
            TILE_READ_HANDLER,
            payload,
            request.timeout_seconds,
        )
        try:
            _reject(invocation, request)
            result = result_type.model_validate(invocation.payload)
            _check_scope(request, result)
            contents = (
                files.read_staged(staged)
                if files is not None and staged is not None
                else None
            )
            if isinstance(result, (TileGetResult, TilemapGetResult)):
                schema = (
                    PixelRegionSnapshot
                    if isinstance(result, TileGetResult)
                    else TileRegionSnapshot
                )
                value = (
                    schema.model_validate_json(contents.payload)
                    if contents
                    else result.snapshot
                )
                expected = (
                    "artifact"
                    if export
                    else "summary"
                    if isinstance(request, TilemapGetRequest)
                    and request.rectangle is None
                    else "inline"
                )
                if (
                    result.output_form != expected
                    or result.artifact is not None
                    or (staged is not None and result.snapshot is not None)
                    or ((value is None) != (expected == "summary"))
                ):
                    raise ValueError("Tile Snapshot transport differs from request")
                if (
                    isinstance(request, TilemapGetRequest)
                    and value is not None
                    and value.rectangle != request.rectangle
                ):
                    raise ValueError("Tile Region Snapshot differs from request")
                if (
                    isinstance(result, TileGetResult)
                    and isinstance(value, PixelRegionSnapshot)
                    and (
                        value.rectangle.width != result.tile.image_size.width
                        or value.rectangle.height != result.tile.image_size.height
                        or value.color_mode != result.tile.color_mode
                    )
                ):
                    raise ValueError("Tile Image Snapshot differs from Tile facts")
        except (ValueError, TypeError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Invalid Tile inspection: {exc}",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        if staged is not None:
            assert (
                files is not None
                and destination is not None
                and export is not None
                and contents is not None
            )
            files.ensure_source_separate(Path(request.sprite_file), destination)
            published = files.publish(
                staged, destination, if_exists=export.if_exists, sha256=contents.sha256
            )
            artifact = TileSnapshotArtifact(
                role="pixel-region-snapshot"
                if isinstance(result, TileGetResult)
                else "tile-region-snapshot",
                path=published.path,
                byte_size=published.byte_size,
                sha256=published.sha256,
            )
            return result_type.model_validate(
                {**result.model_dump(), "artifact": artifact.model_dump()}
            )
        return result
    finally:
        if staged is not None and files is not None:
            files.discard(staged)


def list_tilesets(
    request: TilesetListRequest, services: OperationServices
) -> TilesetListResult:
    return _read(request, services, "tileset list", TilesetListResult)


def get_tileset(
    request: TilesetGetRequest, services: OperationServices
) -> TilesetGetResult:
    return _read(request, services, "tileset get", TilesetGetResult)


def get_tile(request: TileGetRequest, services: OperationServices) -> TileGetResult:
    return _read(request, services, "tileset tile get", TileGetResult)


def validate_tileset(
    request: TilesetTargetRequest, services: OperationServices
) -> TilesetValidateResult:
    return _read(request, services, "tileset validate", TilesetValidateResult)


def list_tilemaps(
    request: TilesetListRequest, services: OperationServices
) -> TilemapListResult:
    return _read(request, services, "tilemap list", TilemapListResult)


def get_tilemap(
    request: TilemapGetRequest, services: OperationServices
) -> TilemapGetResult:
    return _read(request, services, "tilemap get", TilemapGetResult)


def validate_tilemap(
    request: TilemapValidateRequest, services: OperationServices
) -> TilemapValidateResult:
    return _read(request, services, "tilemap validate", TilemapValidateResult)


_FAILURES = (
    *RUNTIME_FAILURE_CODES,
    *(spec.code for spec in TILE_FAILURE_SPECS),
    *(spec.code for spec in LAYER_FAILURE_CODE_SPECS),
    "artifact_file_failed",
)
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
    OperationDescriptor(
        "tileset get",
        TilesetGetRequest,
        TilesetGetResult,
        get_tileset,
        lambda result: f"{len(result.tiles)} Tiles",
        TILE_REQUIREMENTS,
        _FAILURES,
    ),
    OperationDescriptor(
        "tileset tile get",
        TileGetRequest,
        TileGetResult,
        get_tile,
        lambda result: f"Tile {result.tile.tile_index}: {result.output_form}",
        TILE_REQUIREMENTS,
        _FAILURES,
        side_effects=("optionally publishes a JSON Snapshot Artifact",),
    ),
    OperationDescriptor(
        "tileset validate",
        TilesetTargetRequest,
        TilesetValidateResult,
        validate_tileset,
        lambda result: f"{len(result.findings)} Findings",
        TILE_REQUIREMENTS,
        _FAILURES,
    ),
    OperationDescriptor(
        "tilemap list",
        TilesetListRequest,
        TilemapListResult,
        list_tilemaps,
        lambda result: f"{len(result.cels)} existing Tilemap Cels",
        TILE_REQUIREMENTS,
        _FAILURES,
    ),
    OperationDescriptor(
        "tilemap get",
        TilemapGetRequest,
        TilemapGetResult,
        get_tilemap,
        lambda result: result.output_form,
        TILE_REQUIREMENTS,
        _FAILURES,
        side_effects=("optionally publishes a JSON Snapshot Artifact",),
    ),
    OperationDescriptor(
        "tilemap validate",
        TilemapValidateRequest,
        TilemapValidateResult,
        validate_tilemap,
        lambda result: f"{len(result.findings)} Findings",
        TILE_REQUIREMENTS,
        _FAILURES,
    ),
)
