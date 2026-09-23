"""Sprite Domain Module contracts, descriptors, use cases, and rendering."""

from pathlib import Path
from typing import Annotated, Literal, cast

from pydantic import Field, TypeAdapter, ValidationError, field_validator

from spa.contracts import PublicModel, RuntimeRequest, RuntimeRequirements
from spa.mutation import TargetCommit
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.ports import (
    KernelInvocationResult,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PostconditionEvidence,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.raster import Point, Rectangle, RgbaColor, Size

InspectionSection = Literal[
    "frames", "tags", "palettes", "layers", "cels", "slices", "tilesets"
]
INSPECTION_SECTIONS: tuple[InspectionSection, ...] = (
    "frames",
    "tags",
    "palettes",
    "layers",
    "cels",
    "slices",
    "tilesets",
)


def _native_sprite_path(value: str) -> str:
    if Path(value).suffix.lower() != ".aseprite":
        raise ValueError("Sprite file must use the .aseprite extension")
    return value


class BackgroundColor(RgbaColor):
    alpha: Literal[255]


class TransparentInitialLayer(PublicModel):
    kind: Literal["transparent"] = "transparent"


class BackgroundInitialLayer(PublicModel):
    kind: Literal["background"] = "background"
    background_color: BackgroundColor


InitialLayer = Annotated[
    TransparentInitialLayer | BackgroundInitialLayer, Field(discriminator="kind")
]


class SpriteCreateRequest(RuntimeRequest):
    target_sprite_file: str = Field(min_length=1)
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)
    color_mode: Literal["rgb"]
    initial_layer: InitialLayer
    overwrite: bool

    _validate_target = field_validator("target_sprite_file")(_native_sprite_path)


class SpriteGetRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)
    inspection_scope: list[InspectionSection]

    _validate_source = field_validator("sprite_file")(_native_sprite_path)

    @field_validator("inspection_scope")
    @classmethod
    def normalize_scope(cls, value: list[InspectionSection]) -> list[InspectionSection]:
        if len(value) != len(set(value)):
            raise ValueError("Inspection Scope cannot contain duplicate sections")
        requested = set(value)
        return [section for section in INSPECTION_SECTIONS if section in requested]

    @property
    def unrequested_sections(self) -> list[InspectionSection]:
        requested = set(self.inspection_scope)
        return [section for section in INSPECTION_SECTIONS if section not in requested]


class SpriteMetadata(PublicModel):
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    color_mode: Literal["rgb", "grayscale", "indexed"]
    frame_count: int = Field(ge=1)
    tag_count: int = Field(ge=0)
    palette_count: int = Field(ge=0)
    layer_count: int = Field(ge=0)
    cel_count: int = Field(ge=0)
    slice_count: int = Field(ge=0)
    tileset_count: int = Field(ge=0)
    transparent_color_index: int = Field(ge=0)
    grid_bounds: Rectangle
    pixel_ratio: Size


class FrameFacts(PublicModel):
    frame_number: int = Field(ge=1)
    duration_ms: int = Field(ge=0)


class TagFacts(PublicModel):
    name: str
    from_frame: int = Field(ge=1)
    to_frame: int = Field(ge=1)
    direction: Literal["forward", "reverse", "ping_pong", "ping_pong_reverse"]
    repeats: int = Field(ge=0, le=65535)
    color: RgbaColor


class PaletteEntry(PublicModel):
    index: int = Field(ge=0)
    color: RgbaColor


class PaletteFacts(PublicModel):
    frame_number: int = Field(ge=1)
    entries: list[PaletteEntry]


class LayerFacts(PublicModel):
    path: list[int] = Field(min_length=1)
    name: str
    opacity: int | None = Field(default=None, ge=0, le=255)
    blend_mode: str | None
    is_image: bool
    is_group: bool
    is_tilemap: bool
    is_reference: bool
    is_visible: bool
    is_editable: bool
    is_continuous: bool
    is_collapsed: bool
    is_transparent: bool
    is_background: bool
    children: list["LayerFacts"]


class CelFacts(PublicModel):
    layer_path: list[int] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    bounds: Rectangle
    opacity: int = Field(ge=0, le=255)
    z_index: int


class SliceKeyFacts(PublicModel):
    frame_number: int = Field(ge=1)
    bounds: Rectangle
    center: Rectangle | None
    pivot: Point | None


class SliceFacts(PublicModel):
    name: str
    data: str
    keys: list[SliceKeyFacts]


class TilesetFacts(PublicModel):
    name: str
    tile_count: int = Field(ge=0)
    base_index: int = Field(ge=0)
    grid_origin: Point
    tile_size: Size


class InspectionScope(PublicModel):
    requested_sections: list[InspectionSection]
    complete_sections: list[InspectionSection]
    unrequested_sections: list[InspectionSection]


class SpriteInspection(PublicModel):
    metadata: SpriteMetadata
    frames: list[FrameFacts] | None
    tags: list[TagFacts] | None
    palettes: list[PaletteFacts] | None
    layers: list[LayerFacts] | None
    cels: list[CelFacts] | None
    slices: list[SliceFacts] | None
    tilesets: list[TilesetFacts] | None


class SpriteCreateResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite create"] = "spa sprite create"
    target_commit: TargetCommit
    persisted_reopen_verified: Literal[True]
    persisted_initial_layer: InitialLayer
    sprite: SpriteInspection


class SpriteGetResult(SpriteInspection):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite get"] = "spa sprite get"
    sprite_file: str
    scope: InspectionScope


SPRITE_CREATE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_create"],
)
SPRITE_GET_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection"],
)
SPRITE_CREATE_FAILURE_CODES = (*RUNTIME_FAILURE_CODES, "target_commit_failed")
SPRITE_INSPECTION_RESOURCE = PackagedResource("inspection", "sprite_inspect.lua")
SPRITE_CREATION_RESOURCE = PackagedResource("creation", "sprite_create_support.lua")
SPRITE_INSPECTION_FIXTURE = PackagedResource(
    "inspection_fixture", "sprite_inspection_fixture.aseprite"
)
SPRITE_PROBE_RESOURCES = (
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_CREATION_RESOURCE,
    SPRITE_INSPECTION_FIXTURE,
)
SPRITE_CREATE_HANDLER = PackagedHandler(
    "sprite_create", (SPRITE_INSPECTION_RESOURCE, SPRITE_CREATION_RESOURCE)
)
SPRITE_GET_HANDLER = PackagedHandler("sprite_get", (SPRITE_INSPECTION_RESOURCE,))


def _inspection_from_kernel(
    invocation: KernelInvocationResult,
) -> SpriteInspection:
    try:
        return SpriteInspection.model_validate(invocation.payload["sprite"])
    except (KeyError, TypeError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Sprite handler returned invalid inspection facts",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc


def _postcondition_failure(
    invocation: KernelInvocationResult, reason: str
) -> RuntimeIssue:
    return RuntimeIssue(
        "postcondition_failed",
        f"Persisted Sprite inspection did not satisfy declared postconditions: {reason}",
        PostconditionEvidence(response_path=invocation.response_path, reason=reason),
        invocation.diagnostics,
    )


def _layer_count(layers: list[LayerFacts]) -> int:
    return sum(1 + _layer_count(layer.children) for layer in layers)


def _section_count(
    section: InspectionSection, value: object, inspection: SpriteInspection
) -> tuple[int, int]:
    expected = {
        "frames": inspection.metadata.frame_count,
        "tags": inspection.metadata.tag_count,
        "palettes": inspection.metadata.palette_count,
        "layers": inspection.metadata.layer_count,
        "cels": inspection.metadata.cel_count,
        "slices": inspection.metadata.slice_count,
        "tilesets": inspection.metadata.tileset_count,
    }[section]
    if not isinstance(value, list):
        raise TypeError(f"Inspection section {section} is not a list")
    actual = (
        _layer_count(cast(list[LayerFacts], value))
        if section == "layers"
        else len(value)
    )
    return actual, expected


def _validated_scope(
    request: SpriteGetRequest,
    inspection: SpriteInspection,
    invocation: KernelInvocationResult,
) -> InspectionScope:
    complete: list[InspectionSection] = []
    for section in request.inspection_scope:
        value = getattr(inspection, section)
        if value is None:
            raise _postcondition_failure(
                invocation, f"requested section {section} was not inspected"
            )
        else:
            actual, expected = _section_count(section, value, inspection)
            if actual != expected:
                raise _postcondition_failure(
                    invocation,
                    f"section {section} has {actual} entries; metadata declares {expected}",
                )
            complete.append(section)
    for section in request.unrequested_sections:
        if getattr(inspection, section) is not None:
            raise _postcondition_failure(
                invocation, f"unrequested section {section} was populated"
            )
    return InspectionScope(
        requested_sections=request.inspection_scope,
        complete_sections=complete,
        unrequested_sections=request.unrequested_sections,
    )


def _validate_created_sprite(
    request: SpriteCreateRequest,
    inspection: SpriteInspection,
    persisted_initial_layer: InitialLayer,
    invocation: KernelInvocationResult,
) -> None:
    metadata = inspection.metadata
    if (
        metadata.width != request.width
        or metadata.height != request.height
        or metadata.color_mode != request.color_mode
        or metadata.frame_count != 1
        or metadata.layer_count != 1
        or metadata.cel_count != 1
        or metadata.tag_count != 0
        or metadata.slice_count != 0
        or metadata.tileset_count != 0
    ):
        raise _postcondition_failure(
            invocation, "persisted Sprite metadata differs from the create request"
        )
    if inspection.layers is None or len(inspection.layers) != 1:
        raise _postcondition_failure(
            invocation, "persisted Sprite does not have exactly one root layer"
        )
    layer = inspection.layers[0]
    if (
        layer.path != [1]
        or not layer.is_image
        or layer.is_group
        or layer.is_tilemap
        or layer.is_reference
        or layer.children
    ):
        raise _postcondition_failure(
            invocation, "persisted initial layer has unexpected native properties"
        )
    if request.initial_layer.kind == "transparent":
        valid_layer = layer.is_transparent and not layer.is_background
    else:
        valid_layer = not layer.is_transparent and layer.is_background
    valid_layer = valid_layer and (
        persisted_initial_layer.model_dump(mode="json")
        == request.initial_layer.model_dump(mode="json")
    )
    if not valid_layer:
        raise _postcondition_failure(
            invocation, "persisted initial layer differs from the create request"
        )


def create_sprite(
    request: SpriteCreateRequest, services: OperationServices
) -> SpriteCreateResult:
    observation = services.probe_runtime(request)
    target = Path(request.target_sprite_file)
    staged = services.target_files.staged_path(target)
    payload = {
        "width": request.width,
        "height": request.height,
        "color_mode": request.color_mode,
        "initial_layer": request.initial_layer.model_dump(mode="json"),
        "staged_sprite_file": str(staged),
        "inspection_scope": list(INSPECTION_SECTIONS),
    }
    try:
        invocation = services.invoke_kernel(
            observation, SPRITE_CREATE_HANDLER, payload, request.timeout_seconds
        )
        inspection = _inspection_from_kernel(invocation)
        try:
            persisted_initial_layer = TypeAdapter(InitialLayer).validate_python(
                invocation.payload["persisted_initial_layer"]
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Packaged Sprite handler returned invalid persisted initial Layer facts",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        create_scope = SpriteGetRequest(
            aseprite=request.aseprite,
            timeout_seconds=request.timeout_seconds,
            sprite_file=request.target_sprite_file,
            inspection_scope=list(INSPECTION_SECTIONS),
        )
        _validated_scope(create_scope, inspection, invocation)
        _validate_created_sprite(
            request, inspection, persisted_initial_layer, invocation
        )
        committed = services.target_files.commit(
            staged, target, overwrite=request.overwrite
        )
        return SpriteCreateResult(
            target_commit=TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
            persisted_reopen_verified=True,
            persisted_initial_layer=persisted_initial_layer,
            sprite=inspection,
        )
    finally:
        services.target_files.discard(staged)


def get_sprite(
    request: SpriteGetRequest, services: OperationServices
) -> SpriteGetResult:
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        SPRITE_GET_HANDLER,
        {
            "sprite_file": request.sprite_file,
            "inspection_scope": request.inspection_scope,
        },
        request.timeout_seconds,
    )
    inspection = _inspection_from_kernel(invocation)
    scope = _validated_scope(request, inspection, invocation)
    return SpriteGetResult(
        **inspection.model_dump(),
        sprite_file=request.sprite_file,
        scope=scope,
    )


SPRITE_OPERATIONS = (
    OperationDescriptor(
        "sprite create",
        SpriteCreateRequest,
        SpriteCreateResult,
        create_sprite,
        lambda result: result.target_commit.target_sprite_file,
        SPRITE_CREATE_REQUIREMENTS,
        SPRITE_CREATE_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "sprite get",
        SpriteGetRequest,
        SpriteGetResult,
        get_sprite,
        lambda result: (
            f"{result.sprite_file}: {result.metadata.width}x{result.metadata.height} "
            f"{result.metadata.color_mode}"
        ),
        SPRITE_GET_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
)
