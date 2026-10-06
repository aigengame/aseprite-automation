"""Sprite Sheet selection, layout and two-file delivery contract."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from spa.authoring.document.sprite import TagFacts
from spa.authoring.document.tag import TagAddress
from spa.authoring.raster.image_snapshot import LayerComposition
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequest
from spa.delivery.export import ExportDestination, ImageArtifact


class SheetRange(PublicModel):
    kind: Literal["range"]
    from_frame: int = Field(ge=1)
    to_frame: int = Field(ge=1)

    @model_validator(mode="after")
    def ordered(self) -> "SheetRange":
        if self.to_frame < self.from_frame:
            raise ValueError("Frame Range must be in timeline order")
        return self


class SheetTag(PublicModel):
    kind: Literal["tag"]
    tag: TagAddress


class AutomaticLayout(PublicModel):
    kind: Literal["horizontal", "vertical", "packed"]


class RowLayout(PublicModel):
    kind: Literal["rows"]
    columns: int = Field(ge=1, le=65535)


class ColumnLayout(PublicModel):
    kind: Literal["columns"]
    rows: int = Field(ge=1, le=65535)


SheetLayout = Annotated[
    AutomaticLayout | RowLayout | ColumnLayout, Field(discriminator="kind")
]


class SheetPadding(PublicModel):
    border: int = Field(ge=0, le=100)
    shape: int = Field(ge=0, le=100)
    inner: int = Field(ge=0, le=100)


class SheetParameters(PublicModel):
    selection: Annotated[SheetRange | SheetTag, Field(discriminator="kind")]
    layer_composition: LayerComposition
    output_color_mode: Literal["rgb", "indexed"]
    layout: SheetLayout
    trim: Literal["none", "sprite", "frame"]
    padding: SheetPadding
    filename_format: str = Field(
        min_length=1,
        pattern=r"^[^{}\x00\r\n]*\{frame0*[01]\}[^{}\x00\r\n]*$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
        description="One native output ordinal token, based at 0 or 1 with optional zero padding.",
    )


class MetadataDestination(PublicModel):
    path: str = Field(
        min_length=6,
        pattern=r"^[^\x00\r\n]+\.json$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    if_exists: Literal["fail", "replace"]


class ExportSheetRequest(SheetParameters, RuntimeRequest):
    source_sprite_file: str = Field(
        min_length=10,
        pattern=r"^[^\x00\r\n]+\.aseprite$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    image_destination: ExportDestination
    metadata_destination: MetadataDestination


class MetadataArtifact(PublicModel):
    role: Literal["metadata"] = "metadata"
    path: str
    media_type: Literal["application/json"] = "application/json"
    format: Literal["aseprite_json_array"] = "aseprite_json_array"
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SheetRect(PublicModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class SheetFrame(PublicModel):
    source_frame: int = Field(ge=1)
    filename: str
    duration_ms: int = Field(ge=1)
    rectangle: SheetRect
    source_rectangle: SheetRect
    source_width: int = Field(gt=0)
    source_height: int = Field(gt=0)


class SheetTagFacts(TagFacts):
    tag_index: int = Field(ge=1)


class ExportSheetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa export sheet"] = "spa export sheet"
    image_destination: ExportDestination
    metadata_destination: MetadataDestination
    requested_parameters: SheetParameters
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    output_color_mode: Literal["rgb", "indexed"]
    color_profile: Literal["none", "srgb", "icc"]
    icc_identity: Literal["linear_srgb", "display_p3"] | None = None
    srgb_rendering_intent: Literal[0] | None = None
    source_frames: list[int]
    source_tags: list[SheetTagFacts]
    selected_tag: SheetTagFacts | None = None
    common_trim: SheetRect | None = None
    effective_background: bool
    frames: list[SheetFrame]
    artifacts: tuple[ImageArtifact, MetadataArtifact]


class SheetRejection(PublicModel):
    kind: Literal["export_sheet"] = "export_sheet"
    reason: str


SHEET_FAILURE_SPECS = (
    FailureCodeSpec(
        "export_sheet_unsupported",
        "The selected Source or native sheet operation cannot satisfy the requested export",
        "execution",
        SheetRejection,
    ),
)
