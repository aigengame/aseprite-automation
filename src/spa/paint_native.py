"""Native Paint contracts and publication; native Tool semantics stay in Lua."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, ValidationError, model_validator

from spa.cel import (
    CEL_SELECT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    CelAddress,
    CelState,
    _reject,
)
from spa.cel_relationship import CelRelationshipRequest
from spa.contracts import (
    CapabilityGap,
    FailureCodeSpec,
    PublicModel,
    RuntimeRequirements,
)
from spa.layer import LAYER_ADDRESS_FAILURE_CODES
from spa.mutation import TargetCommit, source_target_identity_issue
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.ports import (
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    RequestIssue,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.raster import (
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
from spa.sprite import SPRITE_INSPECTION_RESOURCE, SPRITE_PERSISTENCE_RESOURCE


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


class NativePaintInput(PublicModel):
    target: CelAddress
    coordinate_space: Literal["image-pixel"]
    brush: StandardPaintBrush
    color: ColorValue
    ink: PaintInk
    opacity: int = Field(ge=0, le=255)
    clipping: Literal["reject", "clip"] = "reject"
    selection: SelectionApplication | None = None


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


class NativePaintFacts(PublicModel):
    target: CelAddress
    coordinate_space: Literal["image-pixel"]
    brush: PaintBrushFact
    color: ColorValue
    ink: Literal["simple", "alpha-compositing", "copy-color", "lock-alpha"]
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


class PaintLineEvidence(NativePaintFacts, LineGeometry):
    pass


class NativePaintResult(NativePaintFacts):
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
NATIVE_TOOL_RESOURCE = PackagedResource("native_tool", "native_tool.lua")
NATIVE_PAINT_RESOURCE = PackagedResource("native_paint", "paint_native_support.lua")
NATIVE_PAINT_RESOURCES = (
    NATIVE_TOOL_RESOURCE,
    NATIVE_PAINT_RESOURCE,
    CEL_SELECT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    RASTER_COLOR_RESOURCE,
    SELECTION_MASK_RESOURCE,
    EFFECTIVE_PALETTE_RESOURCE,
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_PERSISTENCE_RESOURCE,
    PackagedResource("digest", "digest.lua"),
)
PAINT_LINE_HANDLER = PackagedHandler("paint_line", NATIVE_PAINT_RESOURCES)
PAINT_RECTANGLE_HANDLER = PackagedHandler("paint_rectangle", NATIVE_PAINT_RESOURCES)
PAINT_ELLIPSE_HANDLER = PackagedHandler("paint_ellipse", NATIVE_PAINT_RESOURCES)


def _execute[ResultT: NativePaintResult](
    request: CelRelationshipRequest,
    services: OperationServices,
    handler: PackagedHandler,
    evidence_type: type[NativePaintFacts],
    result_type: type[ResultT],
) -> ResultT:
    assert isinstance(request, NativePaintInput)
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
                "Shading Ink needs explicit Shade configuration",
                PaintCapabilityDetails(
                    gap=CapabilityGap(
                        capability="shading Ink",
                        aseprite_version=observation.aseprite_version,
                        evidence="Native Shade configuration cannot be supplied and restored explicitly",
                    )
                ),
            )
        _reject(
            invocation,
            request.target.layer,
            request.target,
            (request.target.frame_number, request.target.frame_number),
        )
        try:
            evidence = evidence_type.model_validate(invocation.payload)
            brush = request.brush.model_dump() | {
                "angle": getattr(request.brush, "angle", 0)
            }
            if (
                evidence.target != request.target
                or evidence.color != request.color
                or evidence.brush.model_dump() != brush
                or evidence.ink != request.ink
                or evidence.requested_opacity != request.opacity
                or evidence.clipping != request.clipping
                or evidence.selection != request.selection
                or evidence.pixels_requested != evidence.requested_region.pixel_count
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
                raise ValueError(
                    "Native Paint evidence differs from the requested target or coverage"
                )
            if isinstance(request, LineGeometry) and (
                not isinstance(evidence, LineGeometry)
                or evidence.from_point != request.from_point
                or evidence.to != request.to
            ):
                raise ValueError("Native Line geometry differs from the request")
            if isinstance(request, ShapeGeometry) and (
                not isinstance(evidence, ShapeGeometry)
                or evidence.bounds != request.bounds
                or evidence.style != request.style
            ):
                raise ValueError("Native Shape geometry differs from the request")
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


NATIVE_PAINT_OPERATIONS = (
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
    ),
)
