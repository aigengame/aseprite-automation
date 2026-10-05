"""Animation delivery requests, observed receipts, results, and scoped failures."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, field_validator

from spa.authoring.document.sprite import PaletteEntry, TagFacts
from spa.authoring.document.tag import TagAddress
from spa.authoring.raster.image_snapshot import LayerComposition
from spa.contracts.mutation import validate_native_sprite_path
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequest

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
