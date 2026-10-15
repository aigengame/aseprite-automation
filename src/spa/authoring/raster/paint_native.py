"""Native Paint contracts and publication; native Tool semantics stay in Lua."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, ValidationError, model_validator

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.document.cel_contracts import (
    CEL_SUPPORT_RESOURCE,
    CelAddress,
    CelState,
    raise_cel_rejection,
)
from spa.authoring.document.cel_relationship import CelRelationshipRequest
from spa.authoring.document.layer import LAYER_ADDRESS_FAILURE_CODES
from spa.authoring.document.sprite import (
    SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
)
from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import TargetCommit, source_target_identity_issue
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    RequestIssue,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import (
    CapabilityGap,
    FailureCodeSpec,
    PublicModel,
    RuntimeCapability,
    RuntimeRequirements,
)
from spa.contracts.raster import (
    RASTER_COLOR_RESOURCE,
    SELECTION_MASK_RESOURCE,
    ColorValue,
    EffectivePaletteFact,
    ImageContentDigest,
    Point,
    PositiveRectangle,
    Rectangle,
    SelectionApplication,
    SelectionRow,
)


class CirclePaintBrush(PublicModel):
    kind: Literal["circle"]
    size: int = Field(gt=0)


class OrientedPaintBrush(PublicModel):
    kind: Literal["square", "line"]
    size: int = Field(gt=0)
    angle: int = Field(ge=-180, le=180)


StandardPaintBrush = Annotated[
    CirclePaintBrush | OrientedPaintBrush, Field(discriminator="kind")
]
PaintInk = Literal["simple", "alpha-compositing", "copy-color", "lock-alpha", "shading"]


class NativePaintTargetInput(PublicModel):
    target: CelAddress
    coordinate_space: Literal["image-pixel"]
    opacity: int = Field(ge=0, le=255)
    clipping: Literal["reject", "clip"] = "reject"
    selection: SelectionApplication | None = None


class NativePaintInput(NativePaintTargetInput):
    brush: StandardPaintBrush
    color: ColorValue
    ink: PaintInk


class LineGeometry(PublicModel):
    model_config = ConfigDict(serialize_by_alias=True)
    from_point: Point = Field(alias="from")
    to: Point


class PaintLineRequest(CelRelationshipRequest, NativePaintInput, LineGeometry):
    pass


class ShapeGeometry(PublicModel):
    bounds: PositiveRectangle
    style: Literal["outline", "filled"]


class PaintShapeRequest(CelRelationshipRequest, NativePaintInput, ShapeGeometry):
    pass


class GestureGeometry(PublicModel):
    points: list[Point] = Field(min_length=1)
    freehand_algorithm: Literal["regular", "pixel-perfect", "dots"]


class PaintPencilRequest(CelRelationshipRequest, NativePaintInput, GestureGeometry):
    pass


class EraseBehavior(PublicModel):
    kind: Literal["erase"]
    background_color: ColorValue | None = None


class ReplaceForegroundBehavior(PublicModel):
    kind: Literal["replace-foreground-with-background"]
    foreground_color: ColorValue
    background_color: ColorValue


EraserBehavior = Annotated[
    EraseBehavior | ReplaceForegroundBehavior, Field(discriminator="kind")
]


class PaintEraserRequest(
    CelRelationshipRequest, NativePaintTargetInput, GestureGeometry
):
    brush: StandardPaintBrush
    behavior: EraserBehavior


class FillMatching(PublicModel):
    seed: Point
    tolerance: int = Field(ge=0, le=255)
    contiguous: bool
    connectivity: Literal["four-connected", "eight-connected"] | None = None
    refer_to: Literal["active-layer", "all-layers"]
    stop_at_grid: bool

    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"contiguous": {"const": True}}},
                    "then": {
                        "required": ["connectivity"],
                        "properties": {"connectivity": {"type": "string"}},
                    },
                    "else": {"properties": {"connectivity": {"type": "null"}}},
                }
            ]
        }
    )

    @model_validator(mode="after")
    def require_meaningful_connectivity(self) -> "FillMatching":
        if self.contiguous != (self.connectivity is not None):
            raise ValueError(
                "Contiguous Fill requires connectivity; non-contiguous Fill forbids it"
            )
        return self


class PaintFillRequest(CelRelationshipRequest, NativePaintTargetInput, FillMatching):
    color: ColorValue
    ink: PaintInk


class PaintGesture(PublicModel):
    points: list[Point] = Field(min_length=1)
    freehand_algorithm: Literal["regular", "pixel-perfect"]


class PaintContourRequest(CelRelationshipRequest, NativePaintInput, PaintGesture):
    pass


TiledMode = Literal["none", "x", "y", "both"]


class PaintBlurRequest(CelRelationshipRequest, NativePaintTargetInput, PaintGesture):
    brush: StandardPaintBrush
    tiled_mode: TiledMode


class PaintBrushFact(PublicModel):
    kind: Literal["circle", "square", "line"]
    size: int = Field(gt=0)
    angle: int = Field(ge=-180, le=180)


class PaintCoverage(PublicModel):
    bounds: Rectangle
    rows: list[SelectionRow]
    pixel_count: int = Field(ge=0)

    @model_validator(mode="after")
    def count_coverage(self) -> "PaintCoverage":
        if self.pixel_count != sum(run.length for row in self.rows for run in row.runs):
            raise ValueError("Paint coverage count differs from its runs")
        return self


class NativePaintWriteFacts(PublicModel):
    target: CelAddress
    coordinate_space: Literal["image-pixel"]
    requested_opacity: int = Field(ge=0, le=255)
    effective_opacity: int = Field(ge=0, le=255)
    clipping: Literal["reject", "clip"]
    selection: SelectionApplication | None = None
    color_mode: Literal["rgb", "grayscale", "indexed"]
    requested_region: PaintCoverage
    applied_region: PaintCoverage
    clipped_region: PaintCoverage
    selection_excluded_region: PaintCoverage
    pixels_requested: int = Field(ge=0)
    pixels_written: int = Field(ge=0)
    pixels_changed: int = Field(ge=0)
    pixels_skipped_by_bounds: int = Field(ge=0)
    pixels_skipped_by_selection: int = Field(ge=0)
    affected_cels: list[CelState] = Field(min_length=1)
    linked_cels_preserved: Literal[True]
    geometry_unchanged: Literal[True]
    background_opaque: bool
    effective_palettes: list[EffectivePaletteFact]
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest
    persisted_reopen_verified: Literal[True]


class NativePaintFacts(NativePaintWriteFacts):
    brush: PaintBrushFact
    color: ColorValue
    ink: Literal["simple", "alpha-compositing", "copy-color", "lock-alpha"]


class PaintLineEvidence(NativePaintFacts, LineGeometry):
    pass


class NativePaintResult(NativePaintWriteFacts):
    target_commit: TargetCommit


class PaintLineResult(PaintLineEvidence, NativePaintResult):
    status: Literal["success"] = "success"
    operation: Literal["spa paint line"] = "spa paint line"


class PaintShapeEvidence(NativePaintFacts, ShapeGeometry):
    pass


class PaintRectangleResult(PaintShapeEvidence, NativePaintResult):
    status: Literal["success"] = "success"
    operation: Literal["spa paint rectangle"] = "spa paint rectangle"


class PaintEllipseResult(PaintShapeEvidence, NativePaintResult):
    status: Literal["success"] = "success"
    operation: Literal["spa paint ellipse"] = "spa paint ellipse"


class PaintPencilEvidence(NativePaintFacts, GestureGeometry):
    pass


class PaintPencilResult(PaintPencilEvidence, NativePaintResult):
    status: Literal["success"] = "success"
    operation: Literal["spa paint pencil"] = "spa paint pencil"


class PaintEraserEvidence(NativePaintWriteFacts, GestureGeometry):
    brush: PaintBrushFact
    behavior: EraserBehavior
    native_behavior: Literal[
        "alpha-erasure",
        "transparent-index",
        "background-color",
        "foreground-replacement",
    ]
    transparent_index: int | None = Field(default=None, ge=0, le=255)


class PaintEraserResult(PaintEraserEvidence, NativePaintResult):
    status: Literal["success"] = "success"
    operation: Literal["spa paint eraser"] = "spa paint eraser"


class FillSourceScope(PublicModel):
    kind: Literal["active-layer", "all-layers"]
    frame_number: int = Field(gt=0)
    canvas_bounds: PositiveRectangle


class PaintFillEvidence(NativePaintWriteFacts, FillMatching):
    color: ColorValue
    ink: Literal["simple", "alpha-compositing", "copy-color", "lock-alpha"]
    source_scope: FillSourceScope
    effective_grid_cell: PositiveRectangle | None = None


class PaintFillResult(PaintFillEvidence, NativePaintResult):
    status: Literal["success"] = "success"
    operation: Literal["spa paint fill"] = "spa paint fill"


class PaintContourEvidence(NativePaintFacts, PaintGesture):
    pass


class PaintContourResult(PaintContourEvidence, NativePaintResult):
    status: Literal["success"] = "success"
    operation: Literal["spa paint contour"] = "spa paint contour"


class PaintBlurEvidence(NativePaintWriteFacts, PaintGesture):
    brush: PaintBrushFact
    ink: Literal["blur"]
    tiled_mode: TiledMode


class PaintBlurResult(PaintBlurEvidence, NativePaintResult):
    status: Literal["success"] = "success"
    operation: Literal["spa paint blur"] = "spa paint blur"


class PaintCapabilityDetails(PublicModel):
    kind: Literal["paint_capability_gap"] = "paint_capability_gap"
    gap: CapabilityGap


NATIVE_PAINT_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "paint_capability_gap",
        "Requested native Paint capability is unavailable",
        "input",
        PaintCapabilityDetails,
    ),
)
NATIVE_PAINT_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    *LAYER_ADDRESS_FAILURE_CODES,
    "cel_frame_out_of_bounds",
    "cel_unsupported_target",
    "cel_not_found",
    "paint_capability_gap",
    "target_commit_failed",
)
NATIVE_TOOL_RESOURCE = PackagedResource("native_tool", "raster/paint/native_tool.lua")
NATIVE_PAINT_RESOURCE = PackagedResource(
    "native_paint", "raster/paint/paint_native_support.lua"
)
NATIVE_PAINT_RESOURCES = (
    NATIVE_TOOL_RESOURCE,
    NATIVE_PAINT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    RASTER_COLOR_RESOURCE,
    SELECTION_MASK_RESOURCE,
    EFFECTIVE_PALETTE_RESOURCE,
    *SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    DIGEST_RESOURCE,
)
PAINT_LINE_HANDLER = PackagedHandler(
    "paint_line", "raster/paint/paint_line.lua", NATIVE_PAINT_RESOURCES
)
PAINT_RECTANGLE_HANDLER = PackagedHandler(
    "paint_rectangle", "raster/paint/paint_rectangle.lua", NATIVE_PAINT_RESOURCES
)
PAINT_ELLIPSE_HANDLER = PackagedHandler(
    "paint_ellipse", "raster/paint/paint_ellipse.lua", NATIVE_PAINT_RESOURCES
)
PAINT_PENCIL_HANDLER = PackagedHandler(
    "paint_pencil", "raster/paint/paint_pencil.lua", NATIVE_PAINT_RESOURCES
)
PAINT_ERASER_HANDLER = PackagedHandler(
    "paint_eraser", "raster/paint/paint_eraser.lua", NATIVE_PAINT_RESOURCES
)
PAINT_FILL_HANDLER = PackagedHandler(
    "paint_fill", "raster/paint/paint_fill.lua", NATIVE_PAINT_RESOURCES
)
PAINT_CONTOUR_HANDLER = PackagedHandler(
    "paint_contour", "raster/paint/paint_contour.lua", NATIVE_PAINT_RESOURCES
)
PAINT_BLUR_HANDLER = PackagedHandler(
    "paint_blur", "raster/paint/paint_blur.lua", NATIVE_PAINT_RESOURCES
)


_FREEHAND_GAP_REASON = (
    "The requested Freehand Algorithm is unavailable in the selected runtime"
)
_SHADING_GAP_REASON = (
    "SPA does not provide Shading Ink with explicit Shade configuration"
)


def native_paint_capability_gaps(
    version: str,
    capabilities: list[RuntimeCapability] | tuple[RuntimeCapability, ...],
    *,
    contour_available: bool,
) -> list[CapabilityGap]:
    gaps = []
    for tool in ("pencil", "eraser"):
        if f"aseprite_paint_{tool}" not in capabilities:
            continue
        for algorithm in ("regular", "pixel-perfect", "dots"):
            capability = f"aseprite_paint_{tool}_{algorithm.replace('-', '_')}"
            if capability not in capabilities:
                gaps.append(
                    CapabilityGap(
                        capability=f"{tool} {algorithm}",
                        aseprite_version=version,
                        reason=_FREEHAND_GAP_REASON,
                    )
                )
    for capability, reason in (
        (
            "Paint Dynamics",
            "SPA does not provide scripted pressure, velocity, tilt, or dynamic Brush inputs",
        ),
        (
            "Image Brush",
            "SPA does not provide Image Brush masks or patterns",
        ),
        (
            "shading Ink",
            _SHADING_GAP_REASON,
        ),
    ):
        gaps.append(
            CapabilityGap(
                capability=capability, aseprite_version=version, reason=reason
            )
        )
    # Baseline Aseprite reads Gradient options from the GUI Context Bar; a
    # headless call can dereference that absent state. Do not invoke this path.
    gaps.append(
        CapabilityGap(
            capability="spa paint gradient",
            aseprite_version=version,
            reason="SPA does not provide Gradient painting with explicit Gradient Type and Dithering Matrix.",
        )
    )
    if contour_available:
        gaps.append(
            CapabilityGap(
                capability="spa paint contour: Paint Dynamics",
                aseprite_version=version,
                reason="Contour does not support pressure, velocity, tilt, or Paint Dynamics",
            )
        )
    return gaps


def _execute[ResultT: NativePaintResult](
    request: CelRelationshipRequest,
    services: OperationServices,
    handler: PackagedHandler,
    evidence_type: type[NativePaintWriteFacts],
    result_type: type[ResultT],
) -> ResultT:
    assert isinstance(request, NativePaintTargetInput)
    destination = Path(request.target_sprite_file)
    identity = source_target_identity_issue(
        services.target_files,
        Path(request.source_sprite_file),
        destination,
        request.in_place,
    )
    if identity is not None:
        raise RequestIssue([identity])
    observation = services.probe_runtime(request)
    if isinstance(request, GestureGeometry):
        tool = "eraser" if isinstance(request, PaintEraserRequest) else "pencil"
        capability = (
            f"aseprite_paint_{tool}_{request.freehand_algorithm.replace('-', '_')}"
        )
        if capability not in observation.verified_capabilities:
            raise OperationIssue(
                "paint_capability_gap",
                _FREEHAND_GAP_REASON,
                PaintCapabilityDetails(
                    gap=CapabilityGap(
                        capability=f"{tool} {request.freehand_algorithm}",
                        aseprite_version=observation.aseprite_version,
                        reason=_FREEHAND_GAP_REASON,
                    )
                ),
            )
    staged = services.target_files.staged_path(destination)
    payload = request.model_dump(
        mode="json",
        by_alias=True,
        exclude={
            "aseprite",
            "timeout_seconds",
            "target_sprite_file",
            "in_place",
            "overwrite",
        },
    )
    payload["staged_sprite_file"] = str(staged)
    try:
        invocation = services.invoke_kernel(
            observation, handler, payload, request.timeout_seconds
        )
        rejected = invocation.payload.get("rejection")
        if (
            isinstance(rejected, dict)
            and rejected.get("code") == "paint_capability_gap"
        ):
            raise OperationIssue(
                "paint_capability_gap",
                _SHADING_GAP_REASON,
                PaintCapabilityDetails(
                    gap=CapabilityGap(
                        capability="shading Ink",
                        aseprite_version=observation.aseprite_version,
                        reason=_SHADING_GAP_REASON,
                    )
                ),
            )
        raise_cel_rejection(
            invocation,
            request.target.layer,
            request.target,
            (request.target.frame_number, request.target.frame_number),
        )
        try:
            evidence = evidence_type.model_validate(invocation.payload)
            expected = request.model_dump(
                mode="json",
                by_alias=True,
                exclude=set(CelRelationshipRequest.model_fields),
            )
            expected["requested_opacity"] = expected.pop("opacity")
            if "brush" in expected:
                expected["brush"].setdefault("angle", 0)
            observed = evidence.model_dump(mode="json", by_alias=True)
            if any(observed.get(name) != value for name, value in expected.items()):
                raise ValueError("Native Paint evidence differs from the request")
            if (
                evidence.pixels_requested != evidence.requested_region.pixel_count
                or evidence.pixels_written != evidence.applied_region.pixel_count
                or evidence.pixels_skipped_by_bounds
                != evidence.clipped_region.pixel_count
                or evidence.pixels_skipped_by_selection
                != evidence.selection_excluded_region.pixel_count
                or evidence.pixels_requested
                != (
                    evidence.pixels_written
                    + evidence.pixels_skipped_by_bounds
                    + evidence.pixels_skipped_by_selection
                )
                or evidence.pixels_changed > evidence.pixels_written
            ):
                raise ValueError("Native Paint coverage counts are inconsistent")
        except (TypeError, ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Invalid native Paint evidence",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        committed = services.target_files.commit(
            staged, destination, overwrite=request.overwrite
        )
        return result_type(
            **evidence.model_dump(by_alias=True),
            target_commit=TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
        )
    finally:
        services.target_files.discard(staged)


def paint_line(
    request: PaintLineRequest, services: OperationServices
) -> PaintLineResult:
    return _execute(
        request, services, PAINT_LINE_HANDLER, PaintLineEvidence, PaintLineResult
    )


def paint_rectangle(
    request: PaintShapeRequest, services: OperationServices
) -> PaintRectangleResult:
    return _execute(
        request,
        services,
        PAINT_RECTANGLE_HANDLER,
        PaintShapeEvidence,
        PaintRectangleResult,
    )


def paint_ellipse(
    request: PaintShapeRequest, services: OperationServices
) -> PaintEllipseResult:
    return _execute(
        request, services, PAINT_ELLIPSE_HANDLER, PaintShapeEvidence, PaintEllipseResult
    )


def paint_pencil(
    request: PaintPencilRequest, services: OperationServices
) -> PaintPencilResult:
    return _execute(
        request, services, PAINT_PENCIL_HANDLER, PaintPencilEvidence, PaintPencilResult
    )


def paint_eraser(
    request: PaintEraserRequest, services: OperationServices
) -> PaintEraserResult:
    return _execute(
        request, services, PAINT_ERASER_HANDLER, PaintEraserEvidence, PaintEraserResult
    )


def paint_fill(
    request: PaintFillRequest, services: OperationServices
) -> PaintFillResult:
    return _execute(
        request, services, PAINT_FILL_HANDLER, PaintFillEvidence, PaintFillResult
    )


def paint_contour(
    request: PaintContourRequest, services: OperationServices
) -> PaintContourResult:
    return _execute(
        request,
        services,
        PAINT_CONTOUR_HANDLER,
        PaintContourEvidence,
        PaintContourResult,
    )


def paint_blur(
    request: PaintBlurRequest, services: OperationServices
) -> PaintBlurResult:
    return _execute(
        request, services, PAINT_BLUR_HANDLER, PaintBlurEvidence, PaintBlurResult
    )


NATIVE_PAINT_OPERATIONS = (
    OperationDescriptor(
        "paint fill",
        PaintFillRequest,
        PaintFillResult,
        paint_fill,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=["aseprite_paint_fill"],
        ),
        NATIVE_PAINT_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        help_summary="Fill pixels from a seed using native color matching.",
    ),
    OperationDescriptor(
        "paint eraser",
        PaintEraserRequest,
        PaintEraserResult,
        paint_eraser,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=["aseprite_paint_eraser"],
        ),
        NATIVE_PAINT_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        help_summary="Erase pixels along a path with a native brush.",
    ),
    OperationDescriptor(
        "paint pencil",
        PaintPencilRequest,
        PaintPencilResult,
        paint_pencil,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=["aseprite_paint_pencil"],
        ),
        NATIVE_PAINT_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        help_summary="Draw a path with the native Pencil tool.",
    ),
    OperationDescriptor(
        "paint line",
        PaintLineRequest,
        PaintLineResult,
        paint_line,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=["aseprite_paint_line"],
        ),
        NATIVE_PAINT_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        help_summary="Draw a straight line with a native brush.",
    ),
    OperationDescriptor(
        "paint rectangle",
        PaintShapeRequest,
        PaintRectangleResult,
        paint_rectangle,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=["aseprite_paint_rectangle"],
        ),
        NATIVE_PAINT_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        help_summary="Draw a filled or outlined rectangle.",
    ),
    OperationDescriptor(
        "paint ellipse",
        PaintShapeRequest,
        PaintEllipseResult,
        paint_ellipse,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=["aseprite_paint_ellipse"],
        ),
        NATIVE_PAINT_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        help_summary="Draw a filled or outlined ellipse.",
    ),
    OperationDescriptor(
        "paint contour",
        PaintContourRequest,
        PaintContourResult,
        paint_contour,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=["aseprite_paint_contour"],
        ),
        NATIVE_PAINT_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        help_summary="Draw a filled contour from a path.",
    ),
    OperationDescriptor(
        "paint blur",
        PaintBlurRequest,
        PaintBlurResult,
        paint_blur,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=["aseprite_paint_blur"],
        ),
        NATIVE_PAINT_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        help_summary="Blur pixels along a brush path.",
    ),
)


# These candidates have no callable Descriptor. Baseline Aseprite cannot supply
# the requested gesture/footprint semantics; see the native Paint maintenance notes.
_CANDIDATE_GAP_REASONS = {
    "spray": "SPA does not provide Spray painting.",
    "curve": "SPA does not provide curve painting. Use explicit Line segments instead.",
    "polygon": "SPA does not provide polygon painting. Use explicit Line segments instead.",
    "jumble": "SPA does not provide Jumble Ink.",
}


def native_paint_candidate_gaps(aseprite_version: str) -> list[CapabilityGap]:
    """Describe unavailable Paint operations without claiming native compatibility."""
    return [
        CapabilityGap(
            capability=f"spa paint {tool}",
            aseprite_version=aseprite_version,
            reason=reason,
        )
        for tool, reason in _CANDIDATE_GAP_REASONS.items()
    ]
