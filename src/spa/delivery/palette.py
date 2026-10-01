"""Publish independently verified GPL or Indexed PNG Palette Artifacts."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator

from spa.authoring.color.palette import (
    PALETTE_TRANSFORM_HANDLER,
    PaletteChange,
    PaletteTimeline,
)
from spa.authoring.color.palette_file import (
    PALETTE_FILE_RESOURCE,
    GplPaletteFile,
    PaletteFileReceipt,
    PngPaletteFile,
)
from spa.authoring.color.quantization import (
    PALETTE_QUANTIZATION_RESOURCE,
    QUANTIZATION_REQUIREMENTS,
    QuantizationEvidence,
    QuantizationFacts,
    QuantizationOptions,
    reject_quantization,
    validate_quantization,
)
from spa.contracts.mutation import validate_native_sprite_path
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    ArtifactVerificationEvidence,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PaletteFileError,
    ResponseEvidence,
    RuntimeCompatibilityEvidence,
    RuntimeIssue,
)
from spa.contracts.public import (
    CapabilityGap,
    FailureCodeSpec,
    PublicModel,
    RuntimeCapability,
    RuntimeRequest,
    RuntimeRequirements,
)


class GplDestination(GplPaletteFile):
    if_exists: Literal["fail", "replace"]


class PngDestination(PngPaletteFile):
    if_exists: Literal["fail", "replace"]


PaletteDestination = Annotated[
    GplDestination | PngDestination, Field(discriminator="format")
]


class EffectivePaletteSource(PublicModel):
    kind: Literal["effective"]
    frame_number: int = Field(ge=1)


class QuantizedPaletteSource(QuantizationOptions):
    kind: Literal["color-quantization"]
    palette_frame_number: int = Field(ge=1)


PaletteSource = Annotated[
    EffectivePaletteSource | QuantizedPaletteSource, Field(discriminator="kind")
]


class PaletteExportRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    palette_source: PaletteSource
    destination: PaletteDestination


class PaletteExportEvidence(PaletteTimeline):
    palette: PaletteChange
    quantization: QuantizationFacts | None = None


class PaletteExportResult(PaletteExportEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa palette export"] = "spa palette export"
    palette_source: PaletteSource
    destination: PaletteDestination
    artifact: PaletteFileReceipt


class PaletteExportDetails(PublicModel):
    kind: Literal["palette_export"] = "palette_export"
    reason: Literal["indexed_png_capacity"]
    palette_size: int = Field(ge=257)


PALETTE_EXPORT_FAILURE_SPECS = (
    FailureCodeSpec(
        "palette_export_rejected",
        "Indexed PNG cannot represent this complete Palette",
        "input",
        PaletteExportDetails,
    ),
)
PALETTE_EXPORT_HANDLER = PackagedHandler(
    "palette_export",
    "delivery/palette_export.lua",
    (
        *PALETTE_TRANSFORM_HANDLER.support_resources,
        PALETTE_FILE_RESOURCE,
        PALETTE_QUANTIZATION_RESOURCE,
    ),
)


def palette_export_capability_gaps(
    aseprite_version: str, verified_capabilities: list[RuntimeCapability]
) -> list[CapabilityGap]:
    if "aseprite_palette_quantization" in verified_capabilities:
        return []
    return [
        CapabilityGap(
            capability="spa palette export: color-quantization",
            aseprite_version=aseprite_version,
            evidence="Native Palette quantization was not observed; Effective Palette export remains available",
        )
    ]


def export_palette(
    request: PaletteExportRequest, services: OperationServices
) -> PaletteExportResult:
    files, decode = services.artifact_files, services.decode_palette_file
    assert files is not None and decode is not None, (
        "Palette export requires file services"
    )
    destination = files.normalize_destination(request.destination.path)
    source = Path(request.source_sprite_file)
    files.ensure_source_separate(source, destination)
    staged = files.staged_path(destination, if_exists=request.destination.if_exists)
    try:
        observation = services.probe_runtime(request)
        choice = request.palette_source
        if isinstance(choice, QuantizedPaletteSource):
            required = QUANTIZATION_REQUIREMENTS
            missing: tuple[RuntimeCapability, ...] = tuple(
                capability
                for capability in required.required_capabilities
                if capability not in observation.verified_capabilities
            )
            if missing:
                raise RuntimeIssue(
                    "runtime_incompatible",
                    "The selected Palette export source requires native quantization",
                    RuntimeCompatibilityEvidence(
                        aseprite_version=observation.aseprite_version,
                        lua_version=observation.lua_version,
                        api_version=observation.api_version,
                        required_lua_language=required.lua_language,
                        minimum_api_version=required.minimum_api_version,
                        missing_capabilities=missing,
                    ),
                )
        palette_source = choice.model_dump()
        # Addresses cross Lua as decimal text without imposing a new public bound.
        for key in ("frame_number", "palette_frame_number", "max_colors"):
            if key in palette_source:
                palette_source[key] = str(palette_source[key])
        invocation = services.invoke_kernel(
            observation,
            PALETTE_EXPORT_HANDLER,
            {
                "source_sprite_file": request.source_sprite_file,
                "palette_source": palette_source,
                "format": request.destination.format,
                "staged_palette_file": str(staged),
            },
            request.timeout_seconds,
        )
        rejected = invocation.payload.get("rejection")
        if rejected is not None and rejected.get("code") == "palette_export_rejected":
            try:
                details = PaletteExportDetails.model_validate(rejected["details"])
            except (KeyError, ValueError) as exc:
                raise RuntimeIssue(
                    "response_malformed",
                    "Invalid Palette export rejection",
                    ResponseEvidence(invocation.response_path),
                    invocation.diagnostics,
                ) from exc
            raise OperationIssue(
                "palette_export_rejected",
                "Palette exceeds Indexed PNG capacity",
                details,
            )
        reject_quantization(invocation)
        try:
            native = PaletteExportEvidence.model_validate(invocation.payload)
            if isinstance(choice, EffectivePaletteSource):
                if (
                    native.quantization is not None
                    or native.palette not in native.palette_changes
                    or not native.palette.effective_frame_range.from_frame
                    <= choice.frame_number
                    <= native.palette.effective_frame_range.to_frame
                ):
                    raise ValueError("Wrong Effective Palette")
            else:
                if native.quantization is None:
                    raise ValueError("Missing generation facts")
                generated = QuantizationEvidence.model_validate(native.model_dump())
                validate_quantization(
                    generated, choice, choice.palette_frame_number, mutation=False
                )
        except ValueError as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Invalid Palette export evidence",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        artifact = files.read_staged(staged)
        try:
            decoded = decode(artifact.payload, request.destination.format)
        except PaletteFileError as exc:
            raise RuntimeIssue(
                "artifact_verification_failed",
                "Native output is not a valid Palette file",
                ArtifactVerificationEvidence(str(staged), str(exc)),
                invocation.diagnostics,
            ) from exc
        expected = tuple(
            (e.color.red, e.color.green, e.color.blue, e.color.alpha)
            for e in native.palette.entries
        )
        if (
            decoded.entries != expected
            or decoded.byte_size != artifact.byte_size
            or decoded.sha256 != artifact.sha256
        ):
            raise RuntimeIssue(
                "artifact_verification_failed",
                "Native and decoded Palette facts differ",
                ArtifactVerificationEvidence(
                    str(staged), "ordered Entries, size or digest differ"
                ),
                invocation.diagnostics,
            )
        files.ensure_source_separate(source, destination)
        published = files.publish(
            staged,
            destination,
            if_exists=request.destination.if_exists,
            sha256=decoded.sha256,
        )
        return PaletteExportResult(
            **native.model_dump(),
            palette_source=choice,
            destination=request.destination.model_copy(update={"path": published.path}),
            artifact=PaletteFileReceipt(
                path=published.path,
                format=request.destination.format,
                media_type="text/plain"
                if request.destination.format == "gpl"
                else "image/png",
                byte_size=published.byte_size,
                sha256=published.sha256,
            ),
        )
    finally:
        files.discard(staged)


PALETTE_EXPORT_OPERATIONS = (
    OperationDescriptor(
        "palette export",
        PaletteExportRequest,
        PaletteExportResult,
        export_palette,
        lambda result: result.artifact.path,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=[
                "aseprite_sprite_inspection",
                "aseprite_palette_files",
            ],
        ),
        (
            *RUNTIME_FAILURE_CODES,
            "palette_frame_out_of_bounds",
            "palette_change_missing",
            "palette_export_rejected",
            "palette_quantization_rejected",
            "artifact_file_failed",
            "artifact_verification_failed",
        ),
        execution_kind="export",
        side_effects=("publishes one verified Palette Artifact",),
    ),
)
