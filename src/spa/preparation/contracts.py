"""The bounded Preparation Specification and portable reproduction facts."""

from fractions import Fraction
from typing import Annotated, Literal

from pydantic import Field, model_validator

from spa.authoring.color.color_mode import (
    ColorBestFitCriteria,
    DitheringEvidence,
    MappingEvidence,
    RGBMapAlgorithm,
)
from spa.authoring.raster.image import ImageCanvasOffset, ImageCropRectangle
from spa.contracts.public import PublicModel, RuntimeRequest
from spa.contracts.raster import RgbaColor
from spa.contracts.rounding import Rounding
from spa.delivery.export import ExportDestination, ImageArtifact


class RasterSize(PublicModel):
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)


class ExplicitCrop(PublicModel):
    kind: Literal["rectangle"]
    rectangle: ImageCropRectangle


class AutomaticCrop(PublicModel):
    kind: Literal["automatic"]


class ExactResize(RasterSize):
    kind: Literal["size"]


class UniformResize(PublicModel):
    kind: Literal["scale"]
    factor: float = Field(gt=0, allow_inf_nan=False)


class PreparationPalette(PublicModel):
    entries: list[RgbaColor] = Field(min_length=2, max_length=256)
    transparent_index: int = Field(ge=0, le=255)

    @model_validator(mode="after")
    def canonical_transparency(self) -> "PreparationPalette":
        if self.transparent_index >= len(self.entries):
            raise ValueError("Transparent Palette Index must address an entry")
        for index, color in enumerate(self.entries):
            expected_alpha = 0 if index == self.transparent_index else 255
            if color.alpha != expected_alpha or (
                index == self.transparent_index
                and (color.red != 0 or color.green != 0 or color.blue != 0)
            ):
                raise ValueError(
                    "Use exactly one declared RGBA0 entry and opaque remaining entries"
                )
        return self


class PreparationMapping(PublicModel):
    rgb_map_algorithm: RGBMapAlgorithm
    color_best_fit_criteria: ColorBestFitCriteria
    dithering: Literal["none"]


class InputAnchor(ImageCanvasOffset):
    name: str = Field(min_length=1)


class PreparedAnchor(ImageCanvasOffset):
    name: str = Field(min_length=1)


class AnchorAlignment(PublicModel):
    primary_anchor: str = Field(min_length=1)
    position: ImageCanvasOffset


class PreparationSpecification(PublicModel):
    alpha_threshold: int = Field(ge=1, le=255)
    crop: Annotated[ExplicitCrop | AutomaticCrop, Field(discriminator="kind")]
    resize: Annotated[ExactResize | UniformResize, Field(discriminator="kind")]
    rounding: Rounding
    palette: PreparationPalette
    mapping: PreparationMapping
    canvas: RasterSize
    anchors: list[InputAnchor] = Field(
        min_length=1,
        description="Named Points in the original raster's Image Pixel space, before crop or resize.",
    )
    alignment: AnchorAlignment
    output_mode: Literal["rgba", "indexed"]

    @model_validator(mode="after")
    def exact_anchor_names(self) -> "PreparationSpecification":
        names = [anchor.name for anchor in self.anchors]
        if len(set(names)) != len(names) or self.alignment.primary_anchor not in names:
            raise ValueError(
                "Anchor names must be unique and identify the primary anchor"
            )
        return self


class InputIdentity(PublicModel):
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PreparationGeometry(PublicModel):
    crop: ImageCropRectangle
    resized: RasterSize
    offset: ImageCanvasOffset
    canvas: RasterSize
    anchors: list[PreparedAnchor]


class PreparationProfile(PublicModel):
    source_kind: Literal["none", "srgb", "icc"]
    source_icc_identity: Literal["linear_srgb", "display_p3"] | None
    assumption: Literal["srgb"] | None
    effective: Literal["srgb"]
    converted: bool


class PreparationRuntime(PublicModel):
    aseprite_version: str
    api_version: int
    lua_version: str


class PreparedContent(PublicModel):
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)
    output_mode: Literal["rgba", "indexed"]
    color_profile: Literal["srgb"] = "srgb"
    rendering_intent: Literal[0] = 0
    rgba_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stored_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    palette: PreparationPalette
    alpha_min: Literal[0, 255]
    alpha_max: Literal[0, 255]


class ReproductionRecord(PublicModel):
    source_identity: InputIdentity
    specification: PreparationSpecification
    geometry: PreparationGeometry
    runtime: PreparationRuntime
    mapping: MappingEvidence
    dithering: DitheringEvidence
    profile: PreparationProfile
    content: PreparedContent


class InitialPreparation(PublicModel):
    kind: Literal["initial"]


class ReproducePreparation(PublicModel):
    kind: Literal["reproduce"]
    expected: ReproductionRecord


class PrepareRasterRequest(RuntimeRequest):
    raster_file: str = Field(
        min_length=1,
        pattern=r"^[^\x00\r\n]+$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    intent: Annotated[
        InitialPreparation | ReproducePreparation, Field(discriminator="kind")
    ]
    specification: PreparationSpecification
    destination: ExportDestination


class PrepareRasterResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa raster prepare"] = "spa raster prepare"
    raster_file: str
    artifact: ImageArtifact
    reproduction: ReproductionRecord


def _round(value: Fraction, policy: Rounding) -> int:
    whole, remainder = divmod(value.numerator, value.denominator)
    if policy == "floor":
        return whole
    if policy == "ceil":
        return whole + (remainder != 0)
    if policy == "toward-zero":
        return whole + (whole < 0 and remainder != 0)
    return whole + (
        2 * remainder > value.denominator
        or (2 * remainder == value.denominator and whole >= 0)
    )


def preparation_geometry(
    specification: PreparationSpecification, crop: ImageCropRectangle
) -> PreparationGeometry:
    """Apply declared geometry policy without reading or resampling pixels."""
    resize = specification.resize
    if isinstance(resize, ExactResize):
        size = RasterSize(width=resize.width, height=resize.height)
    else:
        factor = Fraction(str(resize.factor))
        size = RasterSize(
            width=_round(crop.width * factor, specification.rounding),
            height=_round(crop.height * factor, specification.rounding),
        )
    anchors = [
        PreparedAnchor(
            name=anchor.name,
            x=_round(
                (Fraction(str(anchor.x)) - crop.x) * size.width / crop.width,
                specification.rounding,
            ),
            y=_round(
                (Fraction(str(anchor.y)) - crop.y) * size.height / crop.height,
                specification.rounding,
            ),
        )
        for anchor in specification.anchors
    ]
    primary = next(
        anchor
        for anchor in anchors
        if anchor.name == specification.alignment.primary_anchor
    )
    offset = ImageCanvasOffset(
        x=specification.alignment.position.x - primary.x,
        y=specification.alignment.position.y - primary.y,
    )
    if (
        offset.x < 0
        or offset.y < 0
        or offset.x + size.width > specification.canvas.width
        or offset.y + size.height > specification.canvas.height
    ):
        raise ValueError("The complete resized raster must fit on the output Canvas")
    return PreparationGeometry(
        crop=crop,
        resized=size,
        offset=offset,
        canvas=specification.canvas,
        anchors=[
            PreparedAnchor(name=a.name, x=a.x + offset.x, y=a.y + offset.y)
            for a in anchors
        ],
    )
