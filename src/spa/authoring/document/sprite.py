"""Sprite Domain Module contracts, descriptors, use cases, and rendering."""

from pathlib import Path
from typing import Annotated, Literal, cast

from pydantic import (
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    source_target_identity_issue,
    validate_native_sprite_path,
)
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PostconditionEvidence,
    RequestIssue,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import (
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
    ValidationIssue,
)
from spa.contracts.raster import Point, PositiveRectangle, Rectangle, RgbaColor, Size

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


class SpriteCreateInput(PublicModel):
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)
    color_mode: Literal["rgb"]
    initial_layer: InitialLayer


class SpriteCreateRequest(RuntimeRequest, SpriteCreateInput):
    target_sprite_file: str = Field(min_length=1)
    overwrite: bool

    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )


class SpriteGetInput(PublicModel):
    inspection_scope: list[InspectionSection]

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


class SpriteGetRequest(RuntimeRequest, SpriteGetInput):
    sprite_file: str = Field(min_length=1)

    _validate_source = field_validator("sprite_file")(validate_native_sprite_path)


class SpriteExpectedFacts(PublicModel):
    width: int | None = Field(default=None, ge=1, le=65535)
    height: int | None = Field(default=None, ge=1, le=65535)
    color_mode: Literal["rgb", "grayscale", "indexed"] | None = None
    frame_count: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_one_fact(self) -> "SpriteExpectedFacts":
        if all(
            value is None
            for value in (self.width, self.height, self.color_mode, self.frame_count)
        ):
            raise ValueError("At least one expected Sprite fact is required")
        return self


class SpriteValidateRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)
    expected: SpriteExpectedFacts

    _validate_source = field_validator("sprite_file")(validate_native_sprite_path)


class SpriteCopyRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    overwrite: bool

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )


class SpriteFlattenRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_commit_intent(self) -> "SpriteFlattenRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class SpriteGeometryRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_commit_intent(self) -> "SpriteGeometryRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class SpriteResizeRequest(SpriteGeometryRequest):
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)


class SpriteCropRequest(SpriteGeometryRequest):
    coordinate_space: Literal["canvas-pixel"]
    rectangle: PositiveRectangle


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
    use_layer_uuids: bool


class FrameFacts(PublicModel):
    frame_number: int = Field(ge=1)
    duration_ms: int = Field(ge=1, le=65535)


TagDirection = Literal["forward", "reverse", "ping_pong", "ping_pong_reverse"]


class TagFacts(PublicModel):
    name: str
    from_frame: int = Field(ge=1)
    to_frame: int = Field(ge=1)
    direction: TagDirection
    repeats: int = Field(ge=0, le=65535)
    color: RgbaColor


class PaletteEntry(PublicModel):
    index: int = Field(ge=0)
    color: RgbaColor


class PaletteFacts(PublicModel):
    frame_number: int = Field(ge=1)
    entries: list[PaletteEntry]


class LayerFacts(PublicModel):
    path: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)
    name: str
    layer_uuid: str | None
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
    bounds: Rectangle = Field(description="Bounds in Canvas Pixel space")
    center: Rectangle | None = Field(
        description="Center relative to the bounds top-left corner"
    )
    pivot: Point | None = Field(
        description="Pivot relative to the bounds top-left corner"
    )


class SliceFacts(PublicModel):
    name: str
    data: str
    color: RgbaColor
    keys: list[SliceKeyFacts]


class TilesetFacts(PublicModel):
    name: str
    tile_count: int = Field(ge=0)
    base_index: int
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


SpriteFactName = Literal["width", "height", "color_mode", "frame_count"]
SpriteFactValue = int | Literal["rgb", "grayscale", "indexed"]


class SpriteFactCheck(PublicModel):
    fact: SpriteFactName
    expected: SpriteFactValue
    actual: SpriteFactValue
    matches: bool


class SpriteValidationFinding(PublicModel):
    kind: Literal["sprite_fact_mismatch"] = "sprite_fact_mismatch"
    subject: Literal["sprite"] = "sprite"
    fact: SpriteFactName
    expected: SpriteFactValue
    actual: SpriteFactValue


class SpriteValidateResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite validate"] = "spa sprite validate"
    sprite_file: str
    valid: bool
    checks: list[SpriteFactCheck]
    findings: list[SpriteValidationFinding]


class SpriteCopyResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite copy"] = "spa sprite copy"
    target_commit: TargetCommit
    persisted_reopen_verified: Literal[True]
    sprite: SpriteInspection


class SpriteFlattenResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite flatten"] = "spa sprite flatten"
    target_commit: TargetCommit
    persisted_reopen_verified: Literal[True]
    before_sprite: SpriteInspection
    sprite: SpriteInspection


class SpriteGeometryResult(PublicModel):
    target_commit: TargetCommit
    persisted_reopen_verified: Literal[True]
    old_canvas: Size
    new_canvas: Size
    before_sprite: SpriteInspection
    sprite: SpriteInspection


class SpriteResizeResult(SpriteGeometryResult):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite resize"] = "spa sprite resize"
    sampling: Literal["nearest_neighbor"] = "nearest_neighbor"
    coordinate_space: Literal["canvas-pixel"] = "canvas-pixel"
    origin: Point


class ClippedCel(PublicModel):
    layer_path: list[int]
    frame_number: int = Field(ge=1)
    before_bounds: Rectangle
    retained_canvas_bounds: Rectangle | None
    after_bounds: Rectangle | None


class SpriteCropResult(SpriteGeometryResult):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite crop"] = "spa sprite crop"
    coordinate_space: Literal["canvas-pixel"] = "canvas-pixel"
    rectangle: PositiveRectangle
    clipped_cels: list[ClippedCel]


class SpriteCopyStagingDetails(PublicModel):
    kind: Literal["sprite_copy_staging"] = "sprite_copy_staging"
    source_sprite_file: str
    target_sprite_file: str


class SpriteUnsupportedContentDetails(PublicModel):
    kind: Literal["sprite_content"] = "sprite_content"
    source_sprite_file: str
    tileset_count: int = Field(ge=0)
    tilemap_layer_count: int = Field(ge=0)


class SpriteGeometryUnsupportedDetails(SpriteUnsupportedContentDetails):
    tilemap_cel_count: int = Field(ge=0)
    tilemap_image_count: int = Field(ge=0)


class SpriteCropBoundsDetails(PublicModel):
    kind: Literal["crop_bounds"] = "crop_bounds"
    rectangle: PositiveRectangle
    canvas: Size


SPRITE_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "sprite_copy_staging_failed",
        "The Source Sprite File could not be copied to Target staging",
        "execution",
        SpriteCopyStagingDetails,
    ),
    FailureCodeSpec(
        "sprite_flatten_unsupported_content",
        "Flatten does not accept a Sprite with Tilesets or Tilemap Layers",
        "input",
        SpriteUnsupportedContentDetails,
    ),
    FailureCodeSpec(
        "sprite_geometry_unsupported_content",
        "Resize and crop do not accept Tilesets or Tilemap content",
        "input",
        SpriteGeometryUnsupportedDetails,
    ),
    FailureCodeSpec(
        "sprite_crop_out_of_bounds",
        "Crop Rectangle must be wholly inside the current Sprite canvas",
        "input",
        SpriteCropBoundsDetails,
    ),
)


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
SPRITE_FLATTEN_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_flatten", "aseprite_sprite_inspection"],
)
SPRITE_RESIZE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_resize", "aseprite_sprite_inspection"],
)
SPRITE_CROP_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_crop", "aseprite_sprite_inspection"],
)
SPRITE_CREATE_FAILURE_CODES = (*RUNTIME_FAILURE_CODES, "target_commit_failed")
SPRITE_INSPECTION_RESOURCE = PackagedResource(
    "inspection", "document/sprite/sprite_inspect.lua"
)
SPRITE_INSPECTION_RESOURCES = (
    SPRITE_INSPECTION_RESOURCE,
    PackagedResource("layer_select", "document/layer/layer_select.lua"),
    PackagedResource("slice_inspect", "document/slice/slice_inspect.lua"),
)
SPRITE_PERSISTENCE_RESOURCE = PackagedResource(
    "persistence", "document/sprite/sprite_persistence.lua"
)
SPRITE_CREATION_RESOURCE = PackagedResource(
    "creation", "document/sprite/sprite_create_support.lua"
)
SPRITE_INSPECTION_FIXTURE = PackagedResource(
    "inspection_fixture", "runtime/fixtures/sprite_inspection_fixture.aseprite"
)
SPRITE_PROBE_RESOURCES = (
    *SPRITE_INSPECTION_RESOURCES,
    SPRITE_CREATION_RESOURCE,
    SPRITE_INSPECTION_FIXTURE,
)
SPRITE_CREATE_HANDLER = PackagedHandler(
    "sprite_create",
    "document/sprite/sprite_create.lua",
    (*SPRITE_INSPECTION_RESOURCES, SPRITE_CREATION_RESOURCE),
)
SPRITE_GET_HANDLER = PackagedHandler(
    "sprite_get", "document/sprite/sprite_get.lua", SPRITE_INSPECTION_RESOURCES
)
SPRITE_FLATTEN_HANDLER = PackagedHandler(
    "sprite_flatten",
    "document/sprite/sprite_flatten.lua",
    (*SPRITE_INSPECTION_RESOURCES, SPRITE_PERSISTENCE_RESOURCE, DIGEST_RESOURCE),
)
SPRITE_GEOMETRY_HANDLER = PackagedHandler(
    "sprite_geometry",
    "document/sprite/sprite_geometry.lua",
    (*SPRITE_INSPECTION_RESOURCES, SPRITE_PERSISTENCE_RESOURCE, DIGEST_RESOURCE),
)


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


def validated_scope(
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


def validate_created_sprite(
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
        validated_scope(create_scope, inspection, invocation)
        validate_created_sprite(
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
    scope = validated_scope(request, inspection, invocation)
    return SpriteGetResult(
        **inspection.model_dump(),
        sprite_file=request.sprite_file,
        scope=scope,
    )


def validate_sprite(
    request: SpriteValidateRequest, services: OperationServices
) -> SpriteValidateResult:
    inspected = get_sprite(
        SpriteGetRequest(
            sprite_file=request.sprite_file,
            inspection_scope=[],
            aseprite=request.aseprite,
            timeout_seconds=request.timeout_seconds,
        ),
        services,
    )
    checks: list[SpriteFactCheck] = []
    findings: list[SpriteValidationFinding] = []
    for fact in ("width", "height", "color_mode", "frame_count"):
        expected = getattr(request.expected, fact)
        if expected is None:
            continue
        actual = getattr(inspected.metadata, fact)
        matches = actual == expected
        checks.append(
            SpriteFactCheck(
                fact=fact, expected=expected, actual=actual, matches=matches
            )
        )
        if not matches:
            findings.append(
                SpriteValidationFinding(fact=fact, expected=expected, actual=actual)
            )
    return SpriteValidateResult(
        sprite_file=request.sprite_file,
        valid=not findings,
        checks=checks,
        findings=findings,
    )


def copy_sprite(
    request: SpriteCopyRequest, services: OperationServices
) -> SpriteCopyResult:
    source = Path(request.source_sprite_file)
    target = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files, source, target, False
    )
    if identity_issue is not None:
        if identity_issue.location == ["in_place"]:
            identity_issue = ValidationIssue(
                location=["target_sprite_file"],
                code=identity_issue.code,
                message="Sprite copy requires a distinct Target Sprite File",
            )
        raise RequestIssue([identity_issue])
    staged = services.target_files.staged_path(target)
    try:
        try:
            services.target_files.stage_copy(source, staged)
        except OSError as exc:
            raise OperationIssue(
                "sprite_copy_staging_failed",
                "Source Sprite File could not be copied to the staged Target",
                SpriteCopyStagingDetails(
                    source_sprite_file=str(source), target_sprite_file=str(target)
                ),
            ) from exc
        observation = services.probe_runtime(request)
        scope_request = SpriteGetRequest(
            sprite_file=str(staged),
            inspection_scope=list(INSPECTION_SECTIONS),
            aseprite=request.aseprite,
            timeout_seconds=request.timeout_seconds,
        )
        invocation = services.invoke_kernel(
            observation,
            SPRITE_GET_HANDLER,
            {
                "sprite_file": str(staged),
                "inspection_scope": scope_request.inspection_scope,
            },
            request.timeout_seconds,
        )
        inspection = _inspection_from_kernel(invocation)
        validated_scope(scope_request, inspection, invocation)
        committed = services.target_files.commit(
            staged, target, overwrite=request.overwrite
        )
        return SpriteCopyResult(
            target_commit=TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
            persisted_reopen_verified=True,
            sprite=inspection,
        )
    finally:
        services.target_files.discard(staged)


def flatten_sprite(
    request: SpriteFlattenRequest, services: OperationServices
) -> SpriteFlattenResult:
    source = Path(request.source_sprite_file)
    target = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files, source, target, request.in_place
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    staged = services.target_files.staged_path(target)
    observation = services.probe_runtime(request)
    try:
        invocation = services.invoke_kernel(
            observation,
            SPRITE_FLATTEN_HANDLER,
            {
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(staged),
            },
            request.timeout_seconds,
        )
        rejection = invocation.payload.get("rejection")
        if rejection is not None:
            try:
                details = SpriteUnsupportedContentDetails.model_validate(
                    {
                        "source_sprite_file": request.source_sprite_file,
                        **rejection,
                    }
                )
            except (TypeError, ValidationError) as exc:
                raise RuntimeIssue(
                    "response_malformed",
                    "Packaged Sprite flatten handler returned invalid content rejection",
                    ResponseEvidence(response_path=invocation.response_path),
                    invocation.diagnostics,
                ) from exc
            raise OperationIssue(
                "sprite_flatten_unsupported_content",
                "Sprite flatten does not accept Tilesets or Tilemap Layers",
                details,
            )
        try:
            before = SpriteInspection.model_validate(
                invocation.payload["before_sprite"]
            )
            after = SpriteInspection.model_validate(invocation.payload["sprite"])
            if invocation.payload["persisted_reopen_verified"] is not True:
                raise ValueError("staged Sprite was not reopened")
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Packaged Sprite flatten handler returned invalid inspection facts",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        scope = SpriteGetRequest(
            sprite_file=request.source_sprite_file,
            inspection_scope=list(INSPECTION_SECTIONS),
        )
        validated_scope(scope, before, invocation)
        validated_scope(scope, after, invocation)
        committed = services.target_files.commit(
            staged, target, overwrite=request.overwrite
        )
        return SpriteFlattenResult(
            target_commit=TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
            persisted_reopen_verified=True,
            before_sprite=before,
            sprite=after,
        )
    finally:
        services.target_files.discard(staged)


def _transform_sprite(
    request: SpriteResizeRequest | SpriteCropRequest,
    services: OperationServices,
    operation: Literal["resize", "crop"],
) -> SpriteResizeResult | SpriteCropResult:
    source = Path(request.source_sprite_file)
    target = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files, source, target, request.in_place
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    staged = services.target_files.staged_path(target)
    observation = services.probe_runtime(request)
    payload: dict[str, object] = {
        "operation": operation,
        "source_sprite_file": request.source_sprite_file,
        "staged_sprite_file": str(staged),
    }
    if isinstance(request, SpriteResizeRequest):
        payload.update(width=request.width, height=request.height)
    else:
        payload["rectangle"] = request.rectangle.model_dump(mode="json")
    try:
        invocation = services.invoke_kernel(
            observation, SPRITE_GEOMETRY_HANDLER, payload, request.timeout_seconds
        )
        rejection = invocation.payload.get("rejection")
        if rejection is not None:
            if not isinstance(rejection, dict):
                raise _postcondition_failure(invocation, "invalid geometry rejection")
            kind = rejection.get("kind")
            try:
                if kind == "sprite_content":
                    details = SpriteGeometryUnsupportedDetails.model_validate(
                        {"source_sprite_file": request.source_sprite_file, **rejection}
                    )
                    code = "sprite_geometry_unsupported_content"
                    message = "Sprite contains Tilesets or Tilemap content"
                elif kind == "crop_bounds" and operation == "crop":
                    details = SpriteCropBoundsDetails.model_validate(rejection)
                    code = "sprite_crop_out_of_bounds"
                    message = "Crop Rectangle is outside the current Sprite canvas"
                else:
                    raise ValueError("unknown geometry rejection")
            except (TypeError, ValueError, ValidationError) as exc:
                raise RuntimeIssue(
                    "response_malformed",
                    "Packaged Sprite geometry handler returned invalid rejection",
                    ResponseEvidence(response_path=invocation.response_path),
                    invocation.diagnostics,
                ) from exc
            raise OperationIssue(code, message, details)
        try:
            before = SpriteInspection.model_validate(
                invocation.payload["before_sprite"]
            )
            after = SpriteInspection.model_validate(invocation.payload["sprite"])
            if invocation.payload["persisted_reopen_verified"] is not True:
                raise ValueError("staged Sprite was not reopened")
            clipped_cels = (
                TypeAdapter(list[ClippedCel]).validate_python(
                    invocation.payload["clipped_cels"]
                )
                if isinstance(request, SpriteCropRequest)
                else None
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Packaged Sprite geometry handler returned invalid result facts",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        scope = SpriteGetRequest(
            sprite_file=request.source_sprite_file,
            inspection_scope=list(INSPECTION_SECTIONS),
        )
        validated_scope(scope, before, invocation)
        validated_scope(scope, after, invocation)
        old_canvas = Size(width=before.metadata.width, height=before.metadata.height)
        new_canvas = Size(width=after.metadata.width, height=after.metadata.height)
        expected = (
            Size(width=request.width, height=request.height)
            if isinstance(request, SpriteResizeRequest)
            else Size(width=request.rectangle.width, height=request.rectangle.height)
        )
        if new_canvas != expected:
            raise _postcondition_failure(
                invocation, "persisted canvas differs from request"
            )
        committed = services.target_files.commit(
            staged, target, overwrite=request.overwrite
        )
        common = {
            "target_commit": TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
            "persisted_reopen_verified": True,
            "old_canvas": old_canvas,
            "new_canvas": new_canvas,
            "before_sprite": before,
            "sprite": after,
        }
        if isinstance(request, SpriteResizeRequest):
            return SpriteResizeResult(**common, origin=Point(x=0, y=0))
        assert clipped_cels is not None
        return SpriteCropResult(
            **common,
            rectangle=request.rectangle,
            clipped_cels=clipped_cels,
        )
    finally:
        services.target_files.discard(staged)


def resize_sprite(
    request: SpriteResizeRequest, services: OperationServices
) -> SpriteResizeResult:
    return cast(SpriteResizeResult, _transform_sprite(request, services, "resize"))


def crop_sprite(
    request: SpriteCropRequest, services: OperationServices
) -> SpriteCropResult:
    return cast(SpriteCropResult, _transform_sprite(request, services, "crop"))


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
        plan_eligible=True,
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
        plan_eligible=True,
    ),
    OperationDescriptor(
        "sprite copy",
        SpriteCopyRequest,
        SpriteCopyResult,
        copy_sprite,
        lambda result: result.target_commit.target_sprite_file,
        SPRITE_GET_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "target_commit_failed", "sprite_copy_staging_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "sprite flatten",
        SpriteFlattenRequest,
        SpriteFlattenResult,
        flatten_sprite,
        lambda result: result.target_commit.target_sprite_file,
        SPRITE_FLATTEN_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "sprite_flatten_unsupported_content",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "sprite resize",
        SpriteResizeRequest,
        SpriteResizeResult,
        resize_sprite,
        lambda result: result.target_commit.target_sprite_file,
        SPRITE_RESIZE_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "sprite_geometry_unsupported_content",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "sprite crop",
        SpriteCropRequest,
        SpriteCropResult,
        crop_sprite,
        lambda result: result.target_commit.target_sprite_file,
        SPRITE_CROP_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "sprite_geometry_unsupported_content",
            "sprite_crop_out_of_bounds",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "sprite validate",
        SpriteValidateRequest,
        SpriteValidateResult,
        validate_sprite,
        lambda result: f"{result.sprite_file}: {len(result.findings)} findings",
        SPRITE_GET_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
)
