"""PNG sequence delivery: explicit playback, native rendering, verified publication."""

from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal, NoReturn

from pydantic import ConfigDict, Field, ValidationError, field_validator

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.color.profile import PROFILE_RESOURCES
from spa.authoring.raster.image_snapshot import COMPOSITION_RESOURCE, LayerComposition
from spa.contracts.artifact_set import ArtifactDestination, ArtifactSetPublicationError
from spa.contracts.encoded_animation import AnimationDecodeError
from spa.contracts.mutation import validate_native_sprite_path
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    ArtifactVerificationEvidence,
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

ANIMATION_LIMITS = {
    "frame_occurrences": 1024,
    "canvas_pixels": 1_048_576,
    "total_pixels": 16_777_216,
}


class ExplicitFrames(PublicModel):
    kind: Literal["frames"]
    frame_numbers: list[Annotated[int, Field(ge=1)]] = Field(
        min_length=1, max_length=1024
    )


class SequenceDestination(PublicModel):
    directory: str = Field(min_length=1, pattern=r"^[^\x00\r\n]+$")
    filename_format: str = Field(
        min_length=1,
        description="Literal prefix/suffix plus one {frame0} or {frame1} ordinal, optionally zero-padded, ending in .png.",
    )
    if_exists: Literal["fail", "replace"]


class AnimationExportRequest(RuntimeRequest):
    model_config = ConfigDict(
        json_schema_extra={"x-spa-operation-limits": ANIMATION_LIMITS}
    )
    source_sprite_file: str
    playback: ExplicitFrames
    layer_composition: LayerComposition

    _source = field_validator("source_sprite_file")(validate_native_sprite_path)


class ExportSequenceRequest(AnimationExportRequest):
    destination: SequenceDestination


class FrameOccurrence(PublicModel):
    occurrence: int = Field(ge=1)
    source_frame_number: int = Field(ge=1)
    source_duration_ms: int = Field(ge=1, le=65535)


class ResolvedPlayback(PublicModel):
    mode: Literal["explicit_frames"]
    occurrences: list[FrameOccurrence] = Field(min_length=1, max_length=1024)


class AnimationResolution(PublicModel):
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    color_mode: Literal["rgb", "grayscale", "indexed"]
    color_profile: Literal["none", "srgb", "icc"]
    icc_identity: str | None = None
    playback: ResolvedPlayback
    filenames: list[str]


class NativeSequenceFrame(PublicModel):
    occurrence: int = Field(ge=1)
    source_frame_number: int = Field(ge=1)
    filename: str
    effective_background: bool
    resolved_layer_paths: list[list[int]]


class NativeSequenceOutput(PublicModel):
    resolution: AnimationResolution
    frames: list[NativeSequenceFrame]


class AnimationArtifact(PublicModel):
    role: str
    path: str
    media_type: Literal["image/png", "image/gif"]
    format: Literal["png", "gif"]
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SequenceFrameFacts(NativeSequenceFrame):
    color_mode: Literal["rgb", "grayscale", "indexed"]
    color_profile: Literal["none", "srgb", "icc"]
    alpha_min: int = Field(ge=0, le=255)
    alpha_max: int = Field(ge=0, le=255)


class ExportSequenceResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa export sequence"] = "spa export sequence"
    destination: SequenceDestination
    playback: ResolvedPlayback
    layer_composition: LayerComposition
    width: int
    height: int
    frames: list[SequenceFrameFacts]
    artifacts: list[AnimationArtifact]


class AnimationExportDetails(PublicModel):
    kind: Literal["animation_export"] = "animation_export"
    reason: str
    message: str


class PublicationPathState(PublicModel):
    role: str
    path: str
    existed_before_publication: bool
    state: Literal["published", "not_published", "indeterminate"]
    replaced_existing: bool | None


class PartialPublicationDetails(PublicModel):
    kind: Literal["partial_publication"] = "partial_publication"
    destinations: list[PublicationPathState]


ANIMATION_EXPORT_FAILURE_SPECS = (
    FailureCodeSpec(
        "animation_export_invalid",
        "Animation export cannot satisfy the declared request",
        "input",
        AnimationExportDetails,
    ),
    FailureCodeSpec(
        "partial_publication",
        "Export failed after a final destination changed",
        "execution",
        PartialPublicationDetails,
    ),
)
ANIMATION_SUPPORT = PackagedResource(
    "animation_export", "delivery/animation_export_support.lua"
)
ANIMATION_HANDLER = PackagedHandler(
    "animation_export",
    "delivery/animation_export.lua",
    (
        *PROFILE_RESOURCES,
        EFFECTIVE_PALETTE_RESOURCE,
        COMPOSITION_RESOURCE,
        ANIMATION_SUPPORT,
    ),
)
SEQUENCE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_export_sequence"],
)


def _facts[T: PublicModel](kind: type[T], invocation: KernelInvocationResult) -> T:
    rejected = invocation.payload.get("rejection")
    if isinstance(rejected, dict):
        raise OperationIssue(
            "animation_export_invalid",
            str(rejected["message"]),
            AnimationExportDetails(
                reason=str(rejected["reason"]), message=str(rejected["message"])
            ),
        )
    try:
        return kind.model_validate(invocation.payload)
    except ValidationError as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Animation export returned malformed facts",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc


def _mismatch(path: Path, reason: str) -> NoReturn:
    raise RuntimeIssue(
        "artifact_verification_failed",
        reason,
        ArtifactVerificationEvidence(str(path), reason),
    )


def export_sequence(
    request: ExportSequenceRequest, services: OperationServices
) -> ExportSequenceResult:
    files, sets, decode = (
        services.artifact_files,
        services.artifact_sets,
        services.decode_sequence_png,
    )
    assert files is not None and sets is not None and decode is not None
    runtime = services.probe_runtime(request)
    payload = request.model_dump(exclude_none=True) | {
        "format": "png",
        "phase": "resolve",
        "operation_limits": ANIMATION_LIMITS,
    }
    resolution = _facts(
        AnimationResolution,
        services.invoke_kernel(
            runtime, ANIMATION_HANDLER, payload, request.timeout_seconds
        ),
    )
    if [
        item.source_frame_number for item in resolution.playback.occurrences
    ] != request.playback.frame_numbers:
        _mismatch(
            Path(request.source_sprite_file),
            "Resolved Frames differ from the explicit playback",
        )
    directory = files.normalize_destination(request.destination.directory)
    destinations = tuple(
        ArtifactDestination(
            f"frame-{index:04}", directory / name, request.destination.if_exists
        )
        for index, name in enumerate(resolution.filenames, 1)
    )
    staged = sets.prepare(Path(request.source_sprite_file), destinations)
    try:
        payload.update(
            phase="encode",
            output_directory=str(staged.output_directory),
            evidence_directory=str(staged.evidence_directory),
        )
        invocation = services.invoke_kernel(
            runtime, ANIMATION_HANDLER, payload, request.timeout_seconds
        )
        output = _facts(NativeSequenceOutput, invocation)
        if output.resolution != resolution or len(output.frames) != len(destinations):
            _mismatch(
                staged.output_directory, "Resolved animation changed before encoding"
            )
        contents = sets.verify_set(staged)
        frames = []
        for index, (native, data, name, occurrence) in enumerate(
            zip(
                output.frames,
                contents,
                resolution.filenames,
                resolution.playback.occurrences,
                strict=True,
            ),
            1,
        ):
            path = staged.output_directory / name
            try:
                decoded = decode(data.payload)
            except AnimationDecodeError as exc:
                _mismatch(path, str(exc))
            expected = files.read_staged(
                staged.evidence_directory / f"{index}.pixels"
            ).payload
            if (
                native.occurrence != index
                or native.source_frame_number != occurrence.source_frame_number
                or native.filename != name
                or decoded.width != resolution.width
                or decoded.height != resolution.height
                or decoded.color_mode != resolution.color_mode
                or decoded.color_profile != resolution.color_profile
                or decoded.stored_bytes != expected
            ):
                _mismatch(path, "Decoded PNG differs from its native occurrence")
            alpha = decoded.rgba_bytes[3::4]
            frames.append(
                SequenceFrameFacts(
                    **native.model_dump(),
                    color_mode=decoded.color_mode,
                    color_profile=decoded.color_profile,
                    alpha_min=min(alpha),
                    alpha_max=max(alpha),
                )
            )
        try:
            published = sets.publish(staged, tuple(item.sha256 for item in contents))
        except ArtifactSetPublicationError as exc:
            raise OperationIssue(
                "partial_publication",
                str(exc),
                PartialPublicationDetails(
                    destinations=[
                        PublicationPathState(**asdict(item))
                        for item in exc.destinations
                    ]
                ),
            ) from exc
        return ExportSequenceResult(
            destination=request.destination.model_copy(
                update={"directory": str(directory)}
            ),
            playback=resolution.playback,
            layer_composition=request.layer_composition,
            width=resolution.width,
            height=resolution.height,
            frames=frames,
            artifacts=[
                AnimationArtifact(
                    role=destination.role,
                    media_type="image/png",
                    format="png",
                    **asdict(item),
                )
                for destination, item in zip(destinations, published, strict=True)
            ],
        )
    finally:
        sets.discard(staged)


ANIMATION_EXPORT_OPERATIONS = (
    OperationDescriptor(
        "export sequence",
        ExportSequenceRequest,
        ExportSequenceResult,
        export_sequence,
        lambda result: "\n".join(item.path for item in result.artifacts),
        SEQUENCE_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "animation_export_invalid",
            "artifact_file_failed",
            "artifact_verification_failed",
            "partial_publication",
        ),
        execution_kind="export",
        side_effects=("publishes a complete ordered PNG sequence",),
    ),
)
