"""Static PNG choices and observations for one explicitly composed Frame."""

from typing import Annotated, Literal

from pydantic import Field

from spa.authoring.color.profile import AssignProfileInput, ConvertProfileInput
from spa.authoring.document.slice import SliceAddress
from spa.authoring.raster.image_snapshot import LayerComposition
from spa.contracts.public import PublicModel, RuntimeRequest
from spa.contracts.raster import PositiveRectangle, RgbaColor, Size


class ExportDestination(PublicModel):
    path: str = Field(
        min_length=5,
        pattern=r"^[^\x00\r\n]+\.png$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    if_exists: Literal["fail", "replace"]


class CanvasArea(PublicModel):
    kind: Literal["canvas"]


class RectangleArea(PublicModel):
    kind: Literal["rectangle"]
    rectangle: PositiveRectangle


class SliceArea(PublicModel):
    kind: Literal["slice"]
    slice: SliceAddress


ExportImageArea = Annotated[
    CanvasArea | RectangleArea | SliceArea, Field(discriminator="kind")
]


class AssignExportProfile(AssignProfileInput):
    kind: Literal["assign"]


class ConvertExportProfile(ConvertProfileInput):
    kind: Literal["convert"]


ExportProfile = (
    Literal["preserve"]
    | Annotated[AssignExportProfile | ConvertExportProfile, Field(discriminator="kind")]
)


class ExportImageParameters(PublicModel):
    frame_number: int = Field(ge=1)
    export_image_area: ExportImageArea
    layer_composition: LayerComposition
    composition_color_mode: Literal["preserve", "rgb"]
    color_mode: Literal["preserve"]
    color_profile: ExportProfile
    transparency: Literal["preserve"]


class ExportImageRequest(ExportImageParameters, RuntimeRequest):
    source_sprite_file: str = Field(
        min_length=10,
        pattern=r"^[^\x00\r\n]+\.aseprite$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    destination: ExportDestination


class ImageArtifact(PublicModel):
    role: Literal["image"] = "image"
    path: str
    media_type: Literal["image/png"] = "image/png"
    format: Literal["png"] = "png"
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AlphaChannelFacts(PublicModel):
    present: bool
    minimum: int = Field(ge=0, le=255)
    maximum: int = Field(ge=0, le=255)


class ResolvedImageArea(PublicModel):
    kind: Literal["canvas", "rectangle", "slice"]
    rectangle: PositiveRectangle
    slice_index: int | None = Field(default=None, ge=1)
    slice_name: str | None = None
    key_frame_number: int | None = Field(default=None, ge=1)


class NativeImageFacts(PublicModel):
    frame_number: int = Field(ge=1)
    source_color_mode: Literal["rgb", "grayscale", "indexed"]
    composition_color_mode: Literal["preserve", "rgb"]
    source_canvas: Size
    export_image_area: ResolvedImageArea
    resolved_layer_paths: list[list[int]]
    effective_background: bool
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    color_mode: Literal["rgb", "grayscale", "indexed"]
    color_profile: Literal["none", "srgb", "icc"]
    icc_identity: Literal["linear_srgb", "display_p3"] | None = None
    transparent_index: int | None = Field(default=None, ge=0, le=255)
    palette_entries: list[RgbaColor] = Field(default_factory=list)
    stored_content_digest: str = Field(pattern=r"^[0-9a-f]{16}$")
    alpha_min: int = Field(ge=0, le=255)
    alpha_max: int = Field(ge=0, le=255)
    rendered_byte_size: int = Field(gt=0)


class ExportImageResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa export image"] = "spa export image"
    destination: ExportDestination
    frame_number: int = Field(ge=1)
    requested_parameters: ExportImageParameters
    export_image_area: ResolvedImageArea
    layer_composition: LayerComposition
    composition_color_mode: Literal["preserve", "rgb"]
    source_color_mode: Literal["rgb", "grayscale", "indexed"]
    resolved_layer_paths: list[list[int]]
    effective_background: bool
    color_mode: Literal["rgb", "grayscale", "indexed"]
    color_profile: Literal["none", "srgb", "icc"]
    icc_identity: Literal["linear_srgb", "display_p3"] | None = None
    srgb_rendering_intent: Literal[0] | None = None
    transparent_index: int | None = Field(default=None, ge=0, le=255)
    palette_entries: list[RgbaColor] = Field(default_factory=list)
    alpha_channel: AlphaChannelFacts
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    artifact: ImageArtifact


class ExportImageDetails(PublicModel):
    kind: Literal["export_image"] = "export_image"
    reason: str
