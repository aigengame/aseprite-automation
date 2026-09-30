"""Declared animation inspection and verified continuity-preview export."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from spa.authoring.document.cel import (
    CEL_SELECT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    CelAddress,
)
from spa.authoring.document.layer import (
    LAYER_ADDRESS_FAILURE_CODES,
    LayerAddress,
    LayerTargetDetails,
)
from spa.authoring.document.sprite import SPRITE_INSPECTION_RESOURCE
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
from spa.contracts.raster import Rectangle
from spa.delivery.export import (
    EXPORT_FAILURE_CODE_SPECS,
    EXPORT_SUPPORT,
    AlphaChannelFacts,
    ExportDestination,
)
from spa.delivery.png_publication import staged_png

MAX_AUDIT_OBSERVATIONS = 1024
MAX_AUDIT_OVERLAP_PIXEL_CHECKS = 16_777_216


class AuditLimitDetails(PublicModel):
    kind: Literal["operation_limit"] = "operation_limit"
    unit: Literal["coverage_observations", "overlap_pixel_checks"]
    requested: int = Field(ge=0)
    allowed_minimum: Literal[0] = 0
    allowed_maximum: int = Field(gt=0)


ANIMATION_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "audit_limit_exceeded",
        "Animation Audit exceeded its declared coverage or overlap-pixel limit",
        "input",
        AuditLimitDetails,
    ),
)


class FrameScope(PublicModel):
    from_frame: int = Field(ge=1, strict=True)
    to_frame: int = Field(ge=1, strict=True)


class DurationBounds(PublicModel):
    minimum_ms: int = Field(ge=1, strict=True)
    maximum_ms: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def ordered(self) -> "DurationBounds":
        if self.minimum_ms > self.maximum_ms:
            raise ValueError("duration bounds must be ordered")
        return self


class NonOverlapPair(PublicModel):
    first_layer: LayerAddress
    second_layer: LayerAddress


class AnimationAuditRequest(RuntimeRequest):
    model_config = ConfigDict(
        json_schema_extra={
            "x-spa-audit-limits": {
                "coverage_observations": MAX_AUDIT_OBSERVATIONS,
                "overlap_pixel_checks": MAX_AUDIT_OVERLAP_PIXEL_CHECKS,
            }
        }
    )

    sprite_file: str = Field(min_length=1)
    from_frame: int = Field(ge=1, strict=True)
    to_frame: int = Field(ge=1, strict=True)
    required_cels: list[CelAddress] = Field(default_factory=list)
    duration_bounds: DurationBounds | None = None
    non_overlap: list[NonOverlapPair] = Field(default_factory=list)

    _validate_sprite = field_validator("sprite_file")(validate_native_sprite_path)

    @model_validator(mode="after")
    def declared_scope(self) -> "AnimationAuditRequest":
        if self.from_frame > self.to_frame:
            raise ValueError("Frame Range must be ordered")
        if any(
            target.frame_number < self.from_frame or target.frame_number > self.to_frame
            for target in self.required_cels
        ):
            raise ValueError("required Cel must be inside the declared Frame Range")
        return self


class RequiredCelCoverage(PublicModel):
    layer_path: list[int] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    exists: bool


class DurationCoverage(PublicModel):
    frame_number: int = Field(ge=1)
    duration_ms: int = Field(ge=1)


class OverlapCoverage(PublicModel):
    first_layer_path: list[int] = Field(min_length=1)
    second_layer_path: list[int] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    overlap_pixels: int = Field(ge=0)


class MissingCelFinding(PublicModel):
    kind: Literal["required_cel_missing"]
    layer_path: list[int] = Field(min_length=1)
    frame_number: int = Field(ge=1)


class DurationFinding(PublicModel):
    kind: Literal["duration_out_of_bounds"]
    frame_number: int = Field(ge=1)
    duration_ms: int = Field(ge=1)
    minimum_ms: int = Field(ge=1)
    maximum_ms: int = Field(ge=1)


class OverlapFinding(PublicModel):
    kind: Literal["layer_overlap"]
    first_layer_path: list[int] = Field(min_length=1)
    second_layer_path: list[int] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    overlap_pixels: int = Field(gt=0)


Finding = Annotated[
    MissingCelFinding | DurationFinding | OverlapFinding, Field(discriminator="kind")
]


class AnimationAuditResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa animation audit"] = "spa animation audit"
    sprite_file: str
    complete: Literal[True]
    scope: FrameScope
    required_cels: list[RequiredCelCoverage]
    durations: list[DurationCoverage]
    overlaps: list[OverlapCoverage]
    findings: list[Finding]


class _FramePair(RuntimeRequest):
    earlier_frame: int = Field(ge=1, strict=True)
    later_frame: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def chronological(self) -> "_FramePair":
        if self.earlier_frame >= self.later_frame:
            raise ValueError("earlier_frame must precede later_frame")
        return self


class AnimationCompareRequest(_FramePair):
    sprite_file: str = Field(min_length=1)

    _validate_sprite = field_validator("sprite_file")(validate_native_sprite_path)


class AnimationCompareResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa animation compare"] = "spa animation compare"
    sprite_file: str
    complete: Literal[True]
    earlier_frame: int = Field(ge=1)
    later_frame: int = Field(ge=1)
    color_mode: Literal["rgb"]
    bounds: Rectangle
    differing_pixels: int = Field(ge=0)


class AnimationPreviewRequest(_FramePair):
    source_sprite_file: str = Field(min_length=1)
    destination: ExportDestination

    _validate_sprite = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )


class PreviewArtifact(PublicModel):
    role: Literal["preview"] = "preview"
    path: str
    media_type: Literal["image/png"] = "image/png"
    format: Literal["png"] = "png"
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class NativeRuntime(PublicModel):
    aseprite_version: str
    api_version: int
    lua_version: str
    canonical_path: str


class NativePreviewFacts(PublicModel):
    earlier_frame: int = Field(ge=1)
    later_frame: int = Field(ge=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    color_mode: Literal["rgb"]
    color_profile: Literal["none", "srgb"]
    alpha_min: int = Field(ge=0, le=255)
    alpha_max: int = Field(ge=0, le=255)
    rendered_byte_size: int = Field(gt=0)
    layer_order: list[Literal["later", "earlier"]] = Field(min_length=2, max_length=2)
    earlier_blend_mode: Literal["normal"]
    earlier_opacity: Literal[128]

    @model_validator(mode="after")
    def expected_layer_order(self) -> "NativePreviewFacts":
        if self.layer_order != ["later", "earlier"]:
            raise ValueError("Preview Layer order differs from declared overlay")
        return self


class AnimationPreviewResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa animation preview"] = "spa animation preview"
    destination: ExportDestination
    earlier_frame: int = Field(ge=1)
    later_frame: int = Field(ge=1)
    layer_order: list[Literal["later", "earlier"]] = Field(min_length=2, max_length=2)
    earlier_blend_mode: Literal["normal"]
    earlier_opacity: Literal[128]
    color_mode: Literal["rgb"]
    color_profile: Literal["none", "srgb"]
    alpha_channel: AlphaChannelFacts
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    native_runtime: NativeRuntime
    artifact: PreviewArtifact


ANIMATION_SUPPORT = PackagedResource(
    "animation", "document/animation/animation_support.lua"
)
ANIMATION_HANDLER = PackagedHandler(
    "animation",
    "document/animation/animation.lua",
    (
        ANIMATION_SUPPORT,
        CEL_SUPPORT_RESOURCE,
        CEL_SELECT_RESOURCE,
        SPRITE_INSPECTION_RESOURCE,
        EXPORT_SUPPORT,
    ),
)
AUDIT_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_cel_lifecycle"],
)
RENDER_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_export_image"],
)


def _invoked(request: RuntimeRequest, services: OperationServices, payload: dict):
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation, ANIMATION_HANDLER, payload, request.timeout_seconds
    )
    return observation, invocation


def _payload(invocation: KernelInvocationResult) -> dict:
    rejected = invocation.payload.get("rejection")
    if rejected is None:
        return invocation.payload
    if isinstance(rejected, dict) and rejected.get("code") == "audit_limit_exceeded":
        try:
            details = AuditLimitDetails.model_validate(rejected["details"])
            message = rejected["message"]
            if not isinstance(message, str):
                raise TypeError("rejection message is not text")
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Animation handler returned malformed Operation Limit rejection",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        raise OperationIssue("audit_limit_exceeded", message, details)
    if (
        isinstance(rejected, dict)
        and rejected.get("code") in LAYER_ADDRESS_FAILURE_CODES
    ):
        try:
            address = LayerAddress.model_validate(rejected["address"])
            message = rejected["message"]
            if not isinstance(message, str):
                raise TypeError("rejection message is not text")
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Animation handler returned malformed Layer rejection",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        raise OperationIssue(
            rejected["code"],
            message,
            LayerTargetDetails(address_role="target", address=address),
        )
    raise RuntimeIssue(
        "response_malformed",
        "Animation handler returned an unknown rejection",
        ResponseEvidence(invocation.response_path),
        invocation.diagnostics,
    )


def audit_animation(
    request: AnimationAuditRequest, services: OperationServices
) -> AnimationAuditResult:
    frame_count = request.to_frame - request.from_frame + 1
    observations = (
        len(request.required_cels)
        + (frame_count if request.duration_bounds else 0)
        + len(request.non_overlap) * frame_count
    )
    if observations > MAX_AUDIT_OBSERVATIONS:
        raise OperationIssue(
            "audit_limit_exceeded",
            "Animation Audit exceeds its coverage Observation limit",
            AuditLimitDetails(
                unit="coverage_observations",
                requested=observations,
                allowed_maximum=MAX_AUDIT_OBSERVATIONS,
            ),
        )
    _, invocation = _invoked(
        request,
        services,
        {
            "operation": "audit",
            "max_overlap_pixel_checks": MAX_AUDIT_OVERLAP_PIXEL_CHECKS,
            **request.model_dump(
                include={
                    "sprite_file",
                    "from_frame",
                    "to_frame",
                    "required_cels",
                    "duration_bounds",
                    "non_overlap",
                },
                exclude_none=True,
            ),
        },
    )
    payload = _payload(invocation)
    try:
        result = AnimationAuditResult.model_validate(
            {"sprite_file": request.sprite_file, **payload}
        )
        if result.scope != FrameScope(
            from_frame=request.from_frame, to_frame=request.to_frame
        ):
            raise ValueError("reported Frame coverage differs from request")
        if len(result.required_cels) != len(request.required_cels):
            raise ValueError("required Cel coverage incomplete")
        for requested, inspected in zip(
            request.required_cels, result.required_cels, strict=True
        ):
            if inspected.frame_number != requested.frame_number or (
                requested.layer.layer_path is not None
                and inspected.layer_path != requested.layer.layer_path
            ):
                raise ValueError("required Cel coverage differs from declared target")
        if len(result.durations) != (
            request.to_frame - request.from_frame + 1 if request.duration_bounds else 0
        ):
            raise ValueError("duration coverage incomplete")
        if any(
            inspected.frame_number != number
            for number, inspected in enumerate(result.durations, request.from_frame)
        ):
            raise ValueError("duration coverage differs from declared Frame Range")
        if len(result.overlaps) != len(request.non_overlap) * (
            request.to_frame - request.from_frame + 1
        ):
            raise ValueError("overlap coverage incomplete")
        frame_count = request.to_frame - request.from_frame + 1
        for index, pair in enumerate(request.non_overlap):
            inspected_pair = result.overlaps[
                index * frame_count : (index + 1) * frame_count
            ]
            first_path = inspected_pair[0].first_layer_path
            second_path = inspected_pair[0].second_layer_path
            if (
                first_path == second_path
                or (
                    pair.first_layer.layer_path is not None
                    and first_path != pair.first_layer.layer_path
                )
                or (
                    pair.second_layer.layer_path is not None
                    and second_path != pair.second_layer.layer_path
                )
                or any(
                    item.frame_number != number
                    or item.first_layer_path != first_path
                    or item.second_layer_path != second_path
                    for number, item in enumerate(inspected_pair, request.from_frame)
                )
            ):
                raise ValueError(
                    "overlap coverage differs from declared pair and Frame Range"
                )
    except (ValueError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            f"Animation audit returned incomplete or malformed coverage: {exc}",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc
    return result


def compare_animation(
    request: AnimationCompareRequest, services: OperationServices
) -> AnimationCompareResult:
    _, invocation = _invoked(
        request,
        services,
        {
            "operation": "compare",
            "sprite_file": request.sprite_file,
            "earlier_frame": request.earlier_frame,
            "later_frame": request.later_frame,
        },
    )
    try:
        result = AnimationCompareResult.model_validate(
            {"sprite_file": request.sprite_file, **_payload(invocation)}
        )
        if (
            result.earlier_frame != request.earlier_frame
            or result.later_frame != request.later_frame
            or result.bounds.x != 0
            or result.bounds.y != 0
            or result.differing_pixels > result.bounds.width * result.bounds.height
        ):
            raise ValueError("compare facts differ from requested full Canvas")
    except (ValueError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            f"Animation compare returned malformed facts: {exc}",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc
    return result


def preview_animation(
    request: AnimationPreviewRequest, services: OperationServices
) -> AnimationPreviewResult:
    files = services.artifact_files
    verify_png = services.verify_png
    if files is None or verify_png is None:
        raise RuntimeError("Animation Preview requires Artifact files and PNG verifier")
    with staged_png(
        files,
        verify_png,
        source=Path(request.source_sprite_file),
        destination=request.destination.path,
        if_exists=request.destination.if_exists,
    ) as staged:
        observation, invocation = _invoked(
            request,
            services,
            {
                "operation": "preview",
                "source_sprite_file": request.source_sprite_file,
                "earlier_frame": request.earlier_frame,
                "later_frame": request.later_frame,
                "staged_png_file": str(staged.png_file),
                "staged_rgba_file": str(staged.rgba_file),
            },
        )
        try:
            native = NativePreviewFacts.model_validate(_payload(invocation))
        except ValidationError as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Animation Preview returned malformed native facts: {exc}",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        decoded = staged.verify(
            native,
            invocation,
            matches_expected=(
                native.earlier_frame == request.earlier_frame
                and native.later_frame == request.later_frame
                and native.alpha_min <= native.alpha_max
            ),
            mismatch_message="Decoded Preview PNG differs from native rendered facts",
        )
        published = staged.publish()
        return AnimationPreviewResult(
            destination=ExportDestination(
                path=published.path, if_exists=request.destination.if_exists
            ),
            earlier_frame=native.earlier_frame,
            later_frame=native.later_frame,
            layer_order=native.layer_order,
            earlier_blend_mode=native.earlier_blend_mode,
            earlier_opacity=native.earlier_opacity,
            color_mode=native.color_mode,
            color_profile=decoded.color_profile,
            alpha_channel=AlphaChannelFacts(
                present=decoded.alpha_channel_present,
                minimum=decoded.alpha_min,
                maximum=decoded.alpha_max,
            ),
            width=decoded.width,
            height=decoded.height,
            native_runtime=NativeRuntime(
                aseprite_version=observation.aseprite_version,
                api_version=observation.api_version,
                lua_version=observation.lua_version,
                canonical_path=observation.canonical_path,
            ),
            artifact=PreviewArtifact(
                path=published.path,
                byte_size=published.byte_size,
                sha256=published.sha256,
            ),
        )


ANIMATION_OPERATIONS = (
    OperationDescriptor(
        "animation audit",
        AnimationAuditRequest,
        AnimationAuditResult,
        audit_animation,
        lambda result: f"{len(result.findings)} findings",
        AUDIT_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            *LAYER_ADDRESS_FAILURE_CODES,
            "audit_limit_exceeded",
        ),
    ),
    OperationDescriptor(
        "animation compare",
        AnimationCompareRequest,
        AnimationCompareResult,
        compare_animation,
        lambda result: f"{result.differing_pixels} differing pixels",
        RENDER_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
    OperationDescriptor(
        "animation preview",
        AnimationPreviewRequest,
        AnimationPreviewResult,
        preview_animation,
        lambda result: result.artifact.path,
        RENDER_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, *(spec.code for spec in EXPORT_FAILURE_CODE_SPECS)),
        execution_kind="export",
        side_effects=("publishes one verified PNG Preview Artifact",),
    ),
)
