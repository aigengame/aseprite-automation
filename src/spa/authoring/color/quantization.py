"""Explicit native Color Quantization and verified Palette replacement."""

from pathlib import Path
from typing import Literal

from pydantic import Field

from spa.application.mutation import prepare_mutation
from spa.authoring.color.palette import (
    PALETTE_TRANSFORM_HANDLER,
    PaletteCelUse,
    PaletteChange,
    PaletteMutationRequest,
    PaletteTileUse,
    PaletteTimeline,
    reject_palette,
)
from spa.contracts.mutation import TargetCommit
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
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequirements


class QuantizationOptions(PublicModel):
    max_colors: int = Field(ge=1, le=256)
    with_alpha: bool
    rgb_map_algorithm: Literal["default", "rgb5a3", "octree"]
    new_layer_blending_method: bool


class PaletteQuantizationRequest(PaletteMutationRequest, QuantizationOptions):
    palette_frame_number: int = Field(ge=1)


class QuantizationFacts(PublicModel):
    rendered_frames: list[int] = Field(min_length=1)
    affected_frames: list[int] = Field(min_length=1)
    requested_max_colors: int = Field(ge=1, le=256)
    actual_colors: int = Field(ge=1, le=256)
    with_alpha: bool
    rgb_map_algorithm: Literal["default", "rgb5a3", "octree"]
    effective_rgb_map_algorithm: Literal["rgb5a3", "octree"]
    new_layer_blending_method: bool
    original_transparent_color: int | None = Field(default=None, ge=0, le=255)
    final_transparent_color: int | None = Field(default=None, ge=0, le=255)


class QuantizationEvidence(PaletteTimeline):
    palette: PaletteChange
    quantization: QuantizationFacts


class PaletteQuantizationEvidence(QuantizationEvidence):
    persisted_reopen_verified: Literal[True]


class PaletteQuantizationResult(PaletteQuantizationEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa palette color-quantization"] = (
        "spa palette color-quantization"
    )
    target_commit: TargetCommit


class QuantizationDetails(PublicModel):
    kind: Literal["palette_quantization"] = "palette_quantization"
    palette_frame_number: int = Field(ge=1)
    reason: Literal[
        "transparent_index_changed",
        "transparent_index_out_of_bounds",
        "index_out_of_bounds",
        "color_limit_exceeded",
    ]
    original_palette_size: int = Field(ge=1)
    candidate_palette_size: int = Field(ge=1)
    requested_max_colors: int | None = Field(default=None, ge=1, le=256)
    original_transparent_color: int | None = Field(default=None, ge=0, le=255)
    candidate_transparent_color: int | None = Field(default=None, ge=0, le=255)
    index: int | None = Field(default=None, ge=0)
    cel_uses: list[PaletteCelUse] = Field(default_factory=list)
    tile_uses: list[PaletteTileUse] = Field(default_factory=list)


QUANTIZATION_FAILURE_SPECS = (
    FailureCodeSpec(
        "palette_quantization_rejected",
        "Generated Palette violates the requested color limit or Indexed data constraints",
        "input",
        QuantizationDetails,
    ),
)
PALETTE_QUANTIZATION_RESOURCE = PackagedResource(
    "palette_quantization", "color/palette_quantization.lua"
)
PALETTE_QUANTIZATION_HANDLER = PackagedHandler(
    "palette_quantization",
    "color/palette_transform_run.lua",
    (*PALETTE_TRANSFORM_HANDLER.support_resources, PALETTE_QUANTIZATION_RESOURCE),
)
QUANTIZATION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_sprite_inspection",
        "aseprite_palette_quantization",
    ],
)


def reject_quantization(invocation: KernelInvocationResult) -> None:
    rejected = invocation.payload.get("rejection")
    if rejected is None or rejected.get("code") != "palette_quantization_rejected":
        reject_palette(invocation)
        return
    try:
        details = QuantizationDetails.model_validate(rejected["details"])
    except (KeyError, ValueError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Invalid Quantization rejection",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc
    raise OperationIssue(
        "palette_quantization_rejected",
        rejected.get("message", "Unsafe generated Palette"),
        details,
    )


def validate_quantization(
    evidence: QuantizationEvidence,
    request: QuantizationOptions,
    frame: int,
    *,
    mutation: bool,
) -> None:
    """Bind native generation observations to the explicit request and Palette timeline."""
    facts, palette = evidence.quantization, evidence.palette
    selected = next(
        (p for p in evidence.palette_changes if p.palette_frame_number == frame), None
    )
    if (
        palette != selected
        or facts.rendered_frames != list(range(1, evidence.frame_count + 1))
        or facts.affected_frames
        != list(
            range(
                palette.effective_frame_range.from_frame,
                palette.effective_frame_range.to_frame + 1,
            )
        )
        or facts.requested_max_colors != request.max_colors
        or facts.actual_colors != len(palette.entries)
        or facts.actual_colors > request.max_colors
        or facts.with_alpha != request.with_alpha
        or facts.rgb_map_algorithm != request.rgb_map_algorithm
        or facts.effective_rgb_map_algorithm
        != (
            "octree"
            if request.rgb_map_algorithm == "default"
            else request.rgb_map_algorithm
        )
        or facts.new_layer_blending_method != request.new_layer_blending_method
        or (facts.original_transparent_color is None)
        != (facts.final_transparent_color is None)
        or (
            mutation
            and facts.original_transparent_color != facts.final_transparent_color
        )
    ):
        raise ValueError("Generated Palette evidence differs from the request")


def quantize_palette(
    request: PaletteQuantizationRequest, services: OperationServices
) -> PaletteQuantizationResult:
    completion = prepare_mutation(
        services.target_files,
        Path(request.source_sprite_file),
        Path(request.target_sprite_file),
        in_place=request.in_place,
        overwrite=request.overwrite,
        identity_change_message="Source/Target publication identity changed before Target Commit",
    )
    observation = services.probe_runtime(request)
    with completion as mutation:
        invocation = services.invoke_kernel(
            observation,
            PALETTE_QUANTIZATION_HANDLER,
            {
                "operation": "color-quantization",
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(mutation.staged_sprite_file),
                "palette_frame_number": str(request.palette_frame_number),
                "max_colors": str(request.max_colors),
                "with_alpha": request.with_alpha,
                "rgb_map_algorithm": request.rgb_map_algorithm,
                "new_layer_blending_method": request.new_layer_blending_method,
            },
            request.timeout_seconds,
        )
        reject_quantization(invocation)
        try:
            evidence = PaletteQuantizationEvidence.model_validate(invocation.payload)
            validate_quantization(
                evidence, request, request.palette_frame_number, mutation=True
            )
        except ValueError as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Invalid persisted Quantization evidence",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        return PaletteQuantizationResult(
            **evidence.model_dump(), target_commit=mutation.commit()
        )


QUANTIZATION_OPERATIONS = (
    OperationDescriptor(
        "palette color-quantization",
        PaletteQuantizationRequest,
        PaletteQuantizationResult,
        quantize_palette,
        lambda result: result.target_commit.target_sprite_file,
        QUANTIZATION_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "palette_change_missing",
            "palette_quantization_rejected",
            "palette_persistence_failed",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
