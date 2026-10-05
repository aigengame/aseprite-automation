"""PNG sequence delivery: explicit playback, native rendering, verified publication."""

from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal, NoReturn

from pydantic import ConfigDict, Field, ValidationError, field_validator

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.color.profile import PROFILE_RESOURCES, supported_icc_identity
from spa.authoring.document.sprite import PaletteEntry, TagFacts
from spa.authoring.document.tag import TAG_SELECT_RESOURCE, TagAddress
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
    RuntimeCompatibilityEvidence,
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


class TagTraversal(PublicModel):
    kind: Literal["tag"]
    tag: TagAddress


class SequenceDestination(PublicModel):
    directory: str = Field(min_length=1, pattern=r"^[^\x00\r\n]+$")
    filename_format: str = Field(
        min_length=1,
        description="Literal prefix/suffix plus one {frame0} or {frame1} ordinal, optionally zero-padded, ending in .png.",
    )
    if_exists: Literal["fail", "replace"]


class GifDestination(PublicModel):
    path: str = Field(min_length=1, pattern=r"^[^\x00\r\n]+$")
    if_exists: Literal["fail", "replace"]

    @field_validator("path")
    @classmethod
    def gif_extension(cls, value: str) -> str:
        if Path(value).suffix.lower() != ".gif":
            raise ValueError("GIF destination requires the .gif extension")
        return value


class AnimationExportRequest(RuntimeRequest):
    model_config = ConfigDict(
        json_schema_extra={"x-spa-operation-limits": {**ANIMATION_LIMITS}}
    )
    source_sprite_file: str
    playback: Annotated[ExplicitFrames | TagTraversal, Field(discriminator="kind")]
    layer_composition: LayerComposition

    _source = field_validator("source_sprite_file")(validate_native_sprite_path)


class ExportSequenceRequest(AnimationExportRequest):
    destination: SequenceDestination


class ExportGifRequest(AnimationExportRequest):
    destination: GifDestination


class FrameOccurrence(PublicModel):
    occurrence: int = Field(ge=1)
    source_frame_number: int = Field(ge=1)
    source_duration_ms: int = Field(ge=1, le=65535)


class ResolvedPlayback(PublicModel):
    mode: Literal["explicit_frames", "tag_traversal"]
    tag_index: int | None = Field(default=None, ge=1)
    tag: TagFacts | None = None
    occurrences: list[FrameOccurrence] = Field(min_length=1, max_length=1024)


class AnimationResolution(PublicModel):
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    color_mode: Literal["rgb", "grayscale", "indexed"]
    color_profile: Literal["none", "srgb", "icc"]
    icc_identity: str | None = None
    playback: ResolvedPlayback
    filenames: list[str]


class OccurrencePalette(PublicModel):
    palette_frame_number: int = Field(ge=1)
    transparent_color_index: int = Field(ge=0, le=255)
    entries: list[PaletteEntry] = Field(min_length=1, max_length=256)


class NativeSequenceFrame(PublicModel):
    occurrence: int = Field(ge=1)
    source_frame_number: int = Field(ge=1)
    filename: str
    effective_background: bool
    resolved_layer_paths: list[list[int]]
    effective_palette: OccurrencePalette | None


class NativeSequenceOutput(PublicModel):
    resolution: AnimationResolution
    frames: list[NativeSequenceFrame]


class NativeGifFrame(PublicModel):
    occurrence: int = Field(ge=1)
    source_frame_number: int = Field(ge=1)
    effective_background: bool
    resolved_layer_paths: list[list[int]]


class NativeGifOutput(PublicModel):
    resolution: AnimationResolution
    frames: list[NativeGifFrame]


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
    encoded_palette: list[PaletteEntry] | None
    bit_depth: int
    color_type: int
    icc_identity: str | None
    srgb_rendering_intent: int | None


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


class GifFrameFacts(NativeGifFrame):
    source_duration_ms: int
    encoded_duration_ms: int
    color_table: list[list[int]]
    color_table_source: Literal["global", "local"]
    transparent_color_index: int | None
    disposal_method: int
    encoded_rectangle: list[int]
    changed_rgb_pixels: int


class GifLoop(PublicModel):
    mode: Literal["infinite"] = "infinite"
    encoded_count: Literal[0] = 0


class GifProfile(PublicModel):
    source: Literal["none", "srgb", "icc"]
    source_icc_identity: str | None
    native_conversion: Literal["none", "to_srgb"]
    encoded: Literal["unprofiled"] = "unprofiled"


class ExportGifResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa export gif"] = "spa export gif"
    destination: GifDestination
    playback: ResolvedPlayback
    layer_composition: LayerComposition
    width: int
    height: int
    loop: GifLoop
    color_profile: GifProfile
    quantization: Literal["aseprite_native_lossy"] = "aseprite_native_lossy"
    transparency: Literal["zero_transparent_positive_opaque"] = (
        "zero_transparent_positive_opaque"
    )
    frames: list[GifFrameFacts]
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
GIF_RESOURCE = PackagedResource("animation_gif", "delivery/animation_gif.lua")
ANIMATION_HANDLER = PackagedHandler(
    "animation_export",
    "delivery/animation_export.lua",
    (
        *PROFILE_RESOURCES,
        EFFECTIVE_PALETTE_RESOURCE,
        COMPOSITION_RESOURCE,
        TAG_SELECT_RESOURCE,
        ANIMATION_SUPPORT,
        GIF_RESOURCE,
    ),
)
SEQUENCE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_export_sequence"],
)
GIF_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_export_gif"],
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
    if (
        isinstance(request.playback, ExplicitFrames)
        and [item.source_frame_number for item in resolution.playback.occurrences]
        != request.playback.frame_numbers
    ):
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
            if (
                decoded.icc_bytes is not None
                and supported_icc_identity(decoded.icc_bytes) != resolution.icc_identity
            ):
                _mismatch(
                    path, "Encoded PNG ICC differs from the supported Source identity"
                )
            if decoded.srgb_rendering_intent not in (None, 0):
                _mismatch(
                    path,
                    "Encoded PNG sRGB rendering intent differs from native intent 0",
                )
            encoded_palette = None
            if decoded.color_mode == "indexed":
                palette = native.effective_palette
                if (
                    palette is None
                    or palette.transparent_color_index >= len(palette.entries)
                    or [e.index for e in palette.entries]
                    != list(range(len(palette.entries)))
                ):
                    _mismatch(path, "Native Effective Palette facts are incomplete")
                encoded_palette = [
                    entry.model_copy(deep=True) for entry in palette.entries
                ]
                if not native.effective_background:
                    encoded_palette[palette.transparent_color_index].color.alpha = 0
                expected_entries = tuple(
                    (e.color.red, e.color.green, e.color.blue, e.color.alpha)
                    for e in encoded_palette
                )
                if decoded.entries != expected_entries:
                    _mismatch(
                        path,
                        "Encoded PNG Palette differs from the occurrence Effective Palette",
                    )
            elif native.effective_palette is not None:
                _mismatch(path, "Non-Indexed occurrence returned Indexed Palette facts")
            alpha = decoded.rgba_bytes[3::4]
            frames.append(
                SequenceFrameFacts(
                    **native.model_dump(),
                    color_mode=decoded.color_mode,
                    color_profile=decoded.color_profile,
                    alpha_min=min(alpha),
                    alpha_max=max(alpha),
                    encoded_palette=encoded_palette,
                    bit_depth=decoded.bit_depth,
                    color_type=decoded.color_type,
                    icc_identity=resolution.icc_identity,
                    srgb_rendering_intent=decoded.srgb_rendering_intent,
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


def export_gif(
    request: ExportGifRequest, services: OperationServices
) -> ExportGifResult:
    files, sets, decode = (
        services.artifact_files,
        services.artifact_sets,
        services.decode_gif,
    )
    assert files is not None and sets is not None and decode is not None
    runtime = services.probe_runtime(request)
    payload = request.model_dump(exclude_none=True) | {
        "format": "gif",
        "phase": "resolve",
        "operation_limits": ANIMATION_LIMITS,
    }
    resolution = _facts(
        AnimationResolution,
        services.invoke_kernel(
            runtime, ANIMATION_HANDLER, payload, request.timeout_seconds
        ),
    )
    if (
        resolution.color_profile == "icc"
        and "aseprite_convert_color_profile" not in runtime.verified_capabilities
    ):
        raise RuntimeIssue(
            "runtime_incompatible",
            "GIF ICC input requires native Color Profile conversion to sRGB",
            RuntimeCompatibilityEvidence(
                aseprite_version=runtime.aseprite_version,
                lua_version=runtime.lua_version,
                api_version=runtime.api_version,
                required_lua_language="Lua 5.4",
                minimum_api_version=41,
                missing_capabilities=("aseprite_convert_color_profile",),
            ),
        )
    destination = files.normalize_destination(request.destination.path)
    destinations = (
        ArtifactDestination("animation", destination, request.destination.if_exists),
    )
    staged = sets.prepare(Path(request.source_sprite_file), destinations)
    try:
        payload.update(
            phase="encode",
            output_directory=str(staged.output_directory),
            output_filename=destination.name,
            evidence_directory=str(staged.evidence_directory),
        )
        output = _facts(
            NativeGifOutput,
            services.invoke_kernel(
                runtime, ANIMATION_HANDLER, payload, request.timeout_seconds
            ),
        )
        if output.resolution != resolution or len(output.frames) != len(
            resolution.playback.occurrences
        ):
            _mismatch(destination, "Resolved GIF changed before encoding")
        contents = sets.verify_set(staged)
        try:
            decoded = decode(contents[0].payload)
        except AnimationDecodeError as exc:
            _mismatch(destination, str(exc))
        if (
            (decoded.width, decoded.height) != (resolution.width, resolution.height)
            or len(decoded.frames) != len(output.frames)
            or decoded.loop_count != 0
        ):
            _mismatch(
                destination, "GIF Canvas, occurrence count, or infinite loop differs"
            )
        if any(
            identifier == b"ICCRGBG1012"
            for identifier, _ in decoded.application_extensions
        ):
            _mismatch(destination, "GIF unexpectedly embeds an ICC profile")
        frames = []
        expected_size = resolution.width * resolution.height * 4
        for index, (native, occurrence, observed) in enumerate(
            zip(
                output.frames,
                resolution.playback.occurrences,
                decoded.frames,
                strict=True,
            ),
            1,
        ):
            before = files.read_staged(
                staged.evidence_directory / f"{index}.pixels"
            ).payload
            reopened = files.read_staged(
                staged.evidence_directory / f"{index}.gif-rgba"
            ).payload
            if (
                native.occurrence != index
                or native.source_frame_number != occurrence.source_frame_number
                or observed.duration_ms != occurrence.source_duration_ms // 10 * 10
                or len(before) != expected_size
                or len(reopened) != expected_size
                or len(observed.rgba_bytes) != expected_size
            ):
                _mismatch(
                    destination, "GIF occurrence, timing, or pixel evidence differs"
                )
            alpha = observed.rgba_bytes[3::4]
            if alpha != bytes(255 if value else 0 for value in before[3::4]):
                _mismatch(
                    destination,
                    f"GIF occurrence {index} violates zero-transparent/positive-opaque alpha; native output was not published",
                )
            changed = 0
            for offset in range(0, expected_size, 4):
                actual = observed.rgba_bytes[offset : offset + 4]
                if actual[3] != reopened[offset + 3] or (
                    actual[3] and actual[:3] != reopened[offset : offset + 3]
                ):
                    _mismatch(
                        destination,
                        f"Independent GIF occurrence {index} differs from native decoded color evidence",
                    )
                if actual[3] and actual[:3] != before[offset : offset + 3]:
                    changed += 1
            frames.append(
                GifFrameFacts(
                    **native.model_dump(),
                    source_duration_ms=occurrence.source_duration_ms,
                    encoded_duration_ms=observed.duration_ms,
                    color_table=[list(color) for color in observed.color_table],
                    color_table_source=observed.color_table_source,
                    transparent_color_index=observed.transparent_color_index,
                    disposal_method=observed.disposal_method,
                    encoded_rectangle=list(observed.rectangle),
                    changed_rgb_pixels=changed,
                )
            )
        try:
            published = sets.publish(staged, (contents[0].sha256,))
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
        return ExportGifResult(
            destination=request.destination.model_copy(
                update={"path": str(destination)}
            ),
            playback=resolution.playback,
            layer_composition=request.layer_composition,
            width=resolution.width,
            height=resolution.height,
            loop=GifLoop(),
            color_profile=GifProfile(
                source=resolution.color_profile,
                source_icc_identity=resolution.icc_identity,
                native_conversion="to_srgb"
                if resolution.color_profile == "icc"
                else "none",
            ),
            frames=frames,
            artifacts=[
                AnimationArtifact(
                    role="animation",
                    media_type="image/gif",
                    format="gif",
                    **asdict(published[0]),
                )
            ],
        )
    finally:
        sets.discard(staged)


ANIMATION_EXPORT_OPERATIONS = (
    OperationDescriptor(
        "export gif",
        ExportGifRequest,
        ExportGifResult,
        export_gif,
        lambda result: result.artifacts[0].path,
        GIF_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "animation_export_invalid",
            "artifact_file_failed",
            "artifact_verification_failed",
            "partial_publication",
        ),
        execution_kind="export",
        side_effects=("publishes one verified animated GIF",),
    ),
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
