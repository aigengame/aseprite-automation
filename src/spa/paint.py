"""Paint Domain Module contracts, descriptor, and application orchestration."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from spa.cel import CelAddress as LifecycleCelAddress
from spa.cel import CelTargetDetails
from spa.contracts import (
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.layer import LayerAddress
from spa.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    source_target_identity_issue,
    validate_native_sprite_path,
)
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.ports import (
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
from spa.raster import (
    RASTER_COLOR_RESOURCE,
    SELECTION_MASK_RESOURCE,
    EffectivePaletteFact,
    PixelPatch,
    PixelRun,
    PixelWriteEvidence,
    Point,
    Rectangle,
    SelectionApplication,
)

OneBasedIndex = Annotated[int, Field(ge=1)]
MAX_PATCH_PIXELS = 256


class CelAddress(PublicModel):
    layer_path: list[OneBasedIndex] = Field(min_length=1)
    frame_number: int = Field(ge=1)


class PaintPixelPatch(PixelPatch):
    model_config = ConfigDict(
        json_schema_extra={"x-spa-max-addressed-pixels": MAX_PATCH_PIXELS}
    )

    runs: list[PixelRun] = Field(
        max_length=MAX_PATCH_PIXELS,
        description=(
            "Canonical runs with at most 256 runs and 256 addressed Image Pixels "
            "in total."
        ),
    )


class PaintApplyInput(PublicModel):
    target: CelAddress
    patch: PaintPixelPatch
    clipping: Literal["reject", "clip"] = "reject"
    selection: SelectionApplication | None = None

    @model_validator(mode="after")
    def bound_pixels(self) -> "PaintApplyInput":
        if (
            len(self.patch.runs) > MAX_PATCH_PIXELS
            or sum(run.length for run in self.patch.runs) > MAX_PATCH_PIXELS
        ):
            raise ValueError(
                f"Pixel Patch exceeds the {MAX_PATCH_PIXELS}-pixel Operation Limit"
            )
        return self


class PaintApplyRequest(RuntimeRequest, PaintApplyInput):
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
    def validate_target_commit_intent(self) -> "PaintApplyRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class AffectedCel(PublicModel):
    layer_path: list[OneBasedIndex] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    position: Point
    bounds: Rectangle
    linked_to_target: Literal[True]


class PaintApplyEvidence(PixelWriteEvidence):
    input_form: Literal["inline"]
    persisted_reopen_verified: Literal[True]
    target: CelAddress
    color_mode: Literal["rgb", "grayscale", "indexed"]
    clipping: Literal["reject", "clip"]
    selection: SelectionApplication | None = None
    requested_rectangle: Rectangle
    applied_rectangle: Rectangle
    requested_runs: list[PixelRun]
    applied_runs: list[PixelRun]
    skipped_by_bounds_runs: list[PixelRun]
    skipped_by_selection_runs: list[PixelRun]
    pixel_partition_verified: Literal[True]
    affected_cels: list[AffectedCel] = Field(min_length=1)
    linked_cels_preserved: Literal[True]
    geometry_unchanged: Literal[True]
    background_opaque: bool
    effective_palettes: list[EffectivePaletteFact]


class PaintApplyResult(PaintApplyEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa paint apply"] = "spa paint apply"
    target_commit: TargetCommit


PAINT_APPLY_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_paint_apply"],
)
PAINT_APPLY_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    "cel_not_found",
    "target_commit_failed",
)
PAINT_SUPPORT_RESOURCE = PackagedResource("paint", "paint_apply_support.lua")
DIGEST_RESOURCE = PackagedResource("digest", "digest.lua")
PAINT_PROBE_FIXTURE = PackagedResource("paint_fixture", "paint_apply_fixture.aseprite")
PAINT_PROBE_RESOURCES = (
    PAINT_SUPPORT_RESOURCE,
    RASTER_COLOR_RESOURCE,
    EFFECTIVE_PALETTE_RESOURCE,
    SELECTION_MASK_RESOURCE,
    DIGEST_RESOURCE,
    PAINT_PROBE_FIXTURE,
)
PAINT_APPLY_HANDLER = PackagedHandler(
    "paint_apply",
    (
        PAINT_SUPPORT_RESOURCE,
        RASTER_COLOR_RESOURCE,
        EFFECTIVE_PALETTE_RESOURCE,
        SELECTION_MASK_RESOURCE,
        DIGEST_RESOURCE,
    ),
)


def apply_paint(
    request: PaintApplyRequest, services: OperationServices
) -> PaintApplyResult:
    target_file = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files,
        Path(request.source_sprite_file),
        target_file,
        request.in_place,
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    observation = services.probe_runtime(request)
    staged_file = services.target_files.staged_path(target_file)
    payload = request.model_dump(
        mode="json",
        exclude={
            "aseprite",
            "timeout_seconds",
            "target_sprite_file",
            "in_place",
            "overwrite",
        },
    )
    payload["staged_sprite_file"] = str(staged_file)
    try:
        invocation = services.invoke_kernel(
            observation, PAINT_APPLY_HANDLER, payload, request.timeout_seconds
        )
        rejection = invocation.payload.get("rejection")
        if rejection is not None:
            if (
                isinstance(rejection, dict)
                and rejection.get("code") == "cel_not_found"
                and isinstance(rejection.get("message"), str)
            ):
                raise OperationIssue(
                    "cel_not_found",
                    rejection["message"],
                    CelTargetDetails(
                        target=LifecycleCelAddress(
                            layer=LayerAddress(layer_path=request.target.layer_path),
                            frame_number=request.target.frame_number,
                        )
                    ),
                )
            raise RuntimeIssue(
                "response_malformed",
                "Packaged Paint handler returned an invalid Cel rejection",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            )
        evidence = _paint_evidence(invocation)
        validate_paint_evidence(request, evidence, invocation)
        committed = services.target_files.commit(
            staged_file, target_file, overwrite=request.overwrite
        )
        return PaintApplyResult(
            **evidence.model_dump(),
            target_commit=TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
        )
    finally:
        services.target_files.discard(staged_file)


def _paint_evidence(invocation: KernelInvocationResult) -> PaintApplyEvidence:
    try:
        return PaintApplyEvidence.model_validate(invocation.payload)
    except (TypeError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Paint handler returned invalid mutation evidence",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc


def validate_paint_evidence(
    request: PaintApplyInput,
    evidence: PaintApplyEvidence,
    invocation: KernelInvocationResult,
) -> None:
    requested_pixels = sum(run.length for run in request.patch.runs)
    target_cels = [
        cel
        for cel in evidence.affected_cels
        if (
            cel.layer_path == request.target.layer_path
            and cel.frame_number == request.target.frame_number
        )
    ]
    target_cel = target_cels[0] if len(target_cels) == 1 else None
    valid = (
        evidence.target == request.target
        and evidence.clipping == request.clipping
        and evidence.selection == request.selection
        and evidence.requested_rectangle.model_dump()
        == request.patch.rectangle.model_dump()
        and evidence.requested_runs == request.patch.runs
        and evidence.pixels_requested == requested_pixels
        and evidence.matches_coverage(
            applied=sum(run.length for run in evidence.applied_runs),
            bounds=sum(run.length for run in evidence.skipped_by_bounds_runs),
            selection=sum(run.length for run in evidence.skipped_by_selection_runs),
        )
        and target_cel is not None
    )
    if not valid:
        raise RuntimeIssue(
            "postcondition_failed",
            "Persisted Paint evidence differs from the declared request",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="requested, applied, skipped, or affected-Cel facts disagree",
            ),
            invocation.diagnostics,
        )


PAINT_OPERATIONS = (
    OperationDescriptor(
        "paint apply",
        PaintApplyRequest,
        PaintApplyResult,
        apply_paint,
        lambda result: result.target_commit.target_sprite_file,
        PAINT_APPLY_REQUIREMENTS,
        PAINT_APPLY_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        plan_eligible=True,
        probe_before_execute=False,
    ),
)
