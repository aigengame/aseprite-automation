"""Snapshot composition contracts and staged native mutation orchestration."""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.authoring.document.cel import CelAddress, CelState, _reject
from spa.authoring.document.layer import LAYER_ADDRESS_FAILURE_CODES
from spa.authoring.document.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteGetRequest,
    SpriteInspection,
    validated_scope,
)
from spa.authoring.raster.image_snapshot import (
    SNAPSHOT_SUPPORT_RESOURCES,
    ArtifactSnapshot,
    InlineSnapshot,
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
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    RequestIssue,
    ResponseEvidence,
    RuntimeIssue,
    TargetCommitEvidence,
)
from spa.contracts.public import (
    CapabilityGap,
    FailureCodeSpec,
    PublicModel,
    RuntimeCapability,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.contracts.raster import (
    SELECTION_MASK_RESOURCE,
    EffectivePaletteFact,
    PixelRegionSnapshot,
    PixelWriteEvidence,
    Point,
    PositiveRectangle,
    Rectangle,
    SelectionApplication,
)

BlendMode = Literal[
    "normal",
    "multiply",
    "screen",
    "overlay",
    "darken",
    "lighten",
    "color-dodge",
    "color-burn",
    "hard-light",
    "soft-light",
    "difference",
    "exclusion",
    "hue",
    "saturation",
    "color",
    "luminosity",
    "addition",
    "subtract",
    "divide",
]


class CompositePosition(Point):
    x: int = Field(ge=-(2**31), le=2**31 - 1)
    y: int = Field(ge=-(2**31), le=2**31 - 1)


class PaintCompositeRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    target: CelAddress
    input: Annotated[InlineSnapshot | ArtifactSnapshot, Field(discriminator="kind")]
    position: CompositePosition = Field(
        description="Source origin in target Image Pixels; signed 32-bit integer coordinates"
    )
    opacity: int = Field(ge=0, le=255)
    blend_mode: BlendMode
    clipping: Literal["reject", "clip"] = "reject"
    selection: SelectionApplication | None = None
    palette_frame_number: int | None = Field(
        default=None,
        ge=1,
        description="Indexed only: must equal target.frame_number; selects its Effective Palette",
    )

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_intent(self) -> "PaintCompositeRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class CompositeCoverageRun(Point):
    length: int = Field(ge=1)


class PaintCompositeEvidence(PixelWriteEvidence):
    input_form: Literal["inline", "artifact"]
    target: CelAddress
    color_mode: Literal["rgb", "grayscale", "indexed"]
    position: CompositePosition
    opacity: int = Field(ge=0, le=255)
    blend_mode: BlendMode
    clipping: Literal["reject", "clip"]
    selection: SelectionApplication | None = None
    source_rectangle: PositiveRectangle
    target_rectangle: PositiveRectangle
    clipped_rectangle: Rectangle
    applied_rectangle: Rectangle
    applied_runs: list[CompositeCoverageRun]
    skipped_by_bounds_runs: list[CompositeCoverageRun]
    skipped_by_selection_runs: list[CompositeCoverageRun]
    pixels_requested: int = Field(ge=1)
    composite_palette_basis: EffectivePaletteFact | None
    affected_cels: list[CelState] = Field(min_length=1)
    effective_palettes: list[EffectivePaletteFact]
    native_sharing_preserved: Literal[True]
    geometry_unchanged: Literal[True]
    background_opaque: bool
    persisted_reopen_verified: Literal[True]
    sprite: SpriteInspection


class PaintCompositeResult(PaintCompositeEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa paint composite"] = "spa paint composite"
    target_commit: TargetCommit


class CompositeDetails(PublicModel):
    kind: Literal["paint_composite"] = "paint_composite"
    reason: str


class CompositeCapabilityDetails(PublicModel):
    kind: Literal["paint_composite_capability"] = "paint_composite_capability"
    gap: CapabilityGap


# These modes do not have the requested native Grayscale meaning in the verified
# Aseprite 1.3.18.5 baseline. Keep this support boundary with the Paint Operation.
GRAYSCALE_GAPS = {
    "hue": "Native Grayscale Hue maps to Normal",
    "saturation": "Native Grayscale Saturation maps to Normal",
    "color": "Native Grayscale Color maps to Normal",
    "luminosity": "Native Grayscale Luminosity maps to Normal",
    "addition": "Native Grayscale Addition selects Exclusion in Image:drawImage",
}


def composite_capability_gaps(
    aseprite_version: str, capabilities: Sequence[RuntimeCapability]
) -> list[CapabilityGap]:
    gaps = [
        CapabilityGap(
            capability=f"spa paint composite: grayscale {mode}",
            aseprite_version=aseprite_version,
            evidence=(
                f"Not exposed by SPA. Verified with Aseprite 1.3.18.5: {reason}; "
                "no replacement blender is used."
            ),
        )
        for mode, reason in GRAYSCALE_GAPS.items()
    ] + [
        CapabilityGap(
            capability="spa paint composite: indexed blend-mode/opacity",
            aseprite_version=aseprite_version,
            evidence=(
                "Only normal with opacity=255 is supported. In the Aseprite "
                "1.3.18.5 baseline, native Indexed overlay selects indexes and "
                "ignores other BlendMode/opacity values."
            ),
        )
    ]
    if "aseprite_paint_composite_indexed" not in capabilities:
        gaps.append(
            CapabilityGap(
                capability="spa paint composite: indexed",
                aseprite_version=aseprite_version,
                evidence="The isolated Palette-correct native Indexed route was not observed by the runtime probe.",
            )
        )
    return gaps


COMPOSITE_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "paint_composite_invalid",
        "Snapshot cannot be composited at the declared target",
        "input",
        CompositeDetails,
    ),
    FailureCodeSpec(
        "paint_composite_unsupported",
        "Native composition cannot preserve the requested semantics",
        "input",
        CompositeCapabilityDetails,
    ),
)
COMPOSITE_SUPPORT_RESOURCE = PackagedResource(
    "paint_composite", "paint_composite_support.lua"
)
COMPOSITE_HANDLER = PackagedHandler(
    "paint_composite",
    (
        *SNAPSHOT_SUPPORT_RESOURCES,
        SPRITE_PERSISTENCE_RESOURCE,
        DIGEST_RESOURCE,
        SELECTION_MASK_RESOURCE,
        COMPOSITE_SUPPORT_RESOURCE,
    ),
)
COMPOSITE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_paint_composite",
        "aseprite_sprite_inspection",
        "aseprite_cel_lifecycle",
    ],
)


def composite_paint(
    request: PaintCompositeRequest, services: OperationServices
) -> PaintCompositeResult:
    source, target = Path(request.source_sprite_file), Path(request.target_sprite_file)
    issue = source_target_identity_issue(
        services.target_files, source, target, request.in_place
    )
    if issue is not None:
        raise RequestIssue([issue])
    if isinstance(request.input, InlineSnapshot):
        value = request.input.snapshot
    else:
        assert services.artifact_files is not None
        raw = services.artifact_files.read_input(Path(request.input.path))
        try:
            value = PixelRegionSnapshot.model_validate_json(raw)
        except ValidationError as exc:
            raise OperationIssue(
                "paint_composite_invalid",
                "Input is not a canonical Snapshot",
                CompositeDetails(reason=str(exc)),
            ) from exc
    if value.color_mode != "indexed" and request.palette_frame_number is not None:
        raise OperationIssue(
            "paint_composite_invalid",
            "Only Indexed composition accepts palette_frame_number",
            CompositeDetails(
                reason="palette_frame_number is not applicable to this Color Mode"
            ),
        )
    if (
        value.color_mode == "indexed"
        and request.palette_frame_number != request.target.frame_number
    ):
        raise OperationIssue(
            "paint_composite_invalid",
            "Indexed palette_frame_number must equal the target Cel Frame Number",
            CompositeDetails(
                reason="Indexed composition requires the addressed Frame's Effective Palette"
            ),
        )
    observation = services.probe_runtime(request)
    unsupported = None
    if value.color_mode == "grayscale" and request.blend_mode in GRAYSCALE_GAPS:
        unsupported = f"grayscale {request.blend_mode}"
    elif value.color_mode == "indexed":
        if request.blend_mode != "normal" or request.opacity != 255:
            unsupported = "indexed blend-mode/opacity"
        elif (
            "aseprite_paint_composite_indexed" not in observation.verified_capabilities
        ):
            unsupported = "indexed"
    if unsupported is not None:
        gap = next(
            item
            for item in composite_capability_gaps(
                observation.aseprite_version, observation.verified_capabilities
            )
            if item.capability == f"spa paint composite: {unsupported}"
        )
        raise OperationIssue(
            "paint_composite_unsupported",
            gap.evidence,
            CompositeCapabilityDetails(gap=gap),
        )
    staged = services.target_files.staged_path(target)
    try:
        payload = request.model_dump(
            mode="json",
            exclude_none=True,
            exclude={
                "aseprite",
                "timeout_seconds",
                "target_sprite_file",
                "in_place",
                "overwrite",
                "input",
            },
        )
        payload["staged_sprite_file"] = str(staged)
        payload["input"] = {
            "kind": request.input.kind,
            "snapshot": value.model_dump(mode="json"),
        }
        invocation = services.invoke_kernel(
            observation, COMPOSITE_HANDLER, payload, request.timeout_seconds
        )
        rejected = invocation.payload.get("rejection")
        if (
            isinstance(rejected, dict)
            and isinstance(rejected.get("message"), str)
            and isinstance(rejected.get("code"), str)
            and rejected.get("code")
            in {spec.code for spec in COMPOSITE_FAILURE_CODE_SPECS}
        ):
            if rejected["code"] == "paint_composite_unsupported":
                details: PublicModel = CompositeCapabilityDetails(
                    gap=CapabilityGap(
                        capability=f"spa paint composite: {value.color_mode} {request.blend_mode}",
                        aseprite_version=observation.aseprite_version,
                        evidence=rejected["message"],
                    )
                )
            else:
                details = CompositeDetails(reason=rejected["message"])
            raise OperationIssue(rejected["code"], rejected["message"], details)
        number = request.target.frame_number
        _reject(invocation, request.target.layer, request.target, (number, number))
        try:
            evidence = PaintCompositeEvidence.model_validate(invocation.payload)
            if (
                evidence.input_form != request.input.kind
                or evidence.target.frame_number != number
                or (
                    request.target.layer.layer_path is not None
                    and evidence.target.layer.layer_path
                    != request.target.layer.layer_path
                )
                or evidence.color_mode != value.color_mode
                or evidence.source_rectangle != value.rectangle
                or evidence.position != request.position
                or evidence.opacity != request.opacity
                or evidence.blend_mode != request.blend_mode
                or evidence.clipping != request.clipping
                or evidence.selection != request.selection
                or evidence.pixels_requested
                != value.rectangle.width * value.rectangle.height
                or not evidence.matches_coverage(
                    applied=sum(run.length for run in evidence.applied_runs),
                    bounds=sum(run.length for run in evidence.skipped_by_bounds_runs),
                    selection=sum(
                        run.length for run in evidence.skipped_by_selection_runs
                    ),
                )
                or (
                    value.color_mode == "indexed"
                    and (
                        evidence.composite_palette_basis is None
                        or evidence.composite_palette_basis.frame_number != number
                        or not evidence.effective_palettes
                    )
                )
                or (
                    value.color_mode != "indexed"
                    and (
                        evidence.composite_palette_basis is not None
                        or evidence.effective_palettes
                    )
                )
            ):
                raise ValueError("Composite evidence differs from the request")
        except (ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Invalid Paint Composite evidence: {exc}",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        validated_scope(
            SpriteGetRequest(
                sprite_file=request.target_sprite_file,
                inspection_scope=list(INSPECTION_SECTIONS),
            ),
            evidence.sprite,
            invocation,
        )
        if (
            source_target_identity_issue(
                services.target_files, source, target, request.in_place
            )
            is not None
        ):
            raise RuntimeIssue(
                "target_commit_failed",
                "Source/Target identity changed",
                TargetCommitEvidence(str(target), "source_target_identity_changed"),
            )
        committed = services.target_files.commit(
            staged, target, overwrite=request.overwrite
        )
        return PaintCompositeResult(
            **evidence.model_dump(),
            target_commit=TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
        )
    finally:
        services.target_files.discard(staged)


COMPOSITE_OPERATIONS = (
    OperationDescriptor(
        "paint composite",
        PaintCompositeRequest,
        PaintCompositeResult,
        composite_paint,
        lambda result: result.target_commit.target_sprite_file,
        COMPOSITE_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "artifact_file_failed",
            "cel_not_found",
            "cel_unsupported_target",
            "cel_frame_out_of_bounds",
            *LAYER_ADDRESS_FAILURE_CODES,
            *(spec.code for spec in COMPOSITE_FAILURE_CODE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        probe_before_execute=False,
    ),
)
