"""Canonical Raster values shared by authoring and inspection operations."""

from typing import Annotated, Literal

from pydantic import Field

from spa.contracts import PublicModel


class RgbaColor(PublicModel):
    red: int = Field(ge=0, le=255)
    green: int = Field(ge=0, le=255)
    blue: int = Field(ge=0, le=255)
    alpha: int = Field(ge=0, le=255)


class RgbaColorValue(RgbaColor):
    kind: Literal["rgba"] = "rgba"


class GrayscaleColor(PublicModel):
    kind: Literal["grayscale"] = "grayscale"
    gray: int = Field(ge=0, le=255)
    alpha: int = Field(ge=0, le=255)


class PaletteIndexColor(PublicModel):
    kind: Literal["palette-index"] = "palette-index"
    index: int = Field(ge=0, le=255)


ColorValue = Annotated[
    RgbaColorValue | GrayscaleColor | PaletteIndexColor, Field(discriminator="kind")
]


class Point(PublicModel):
    x: int
    y: int


class Size(PublicModel):
    width: int = Field(ge=0)
    height: int = Field(ge=0)


class Rectangle(Point, Size):
    pass


class PositiveRectangle(Point):
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class PixelRun(Point):
    length: int = Field(ge=1)
    color: ColorValue


class PixelPatch(PublicModel):
    coordinate_space: Literal["image-pixel"]
    rectangle: PositiveRectangle
    runs: list[PixelRun]


class SelectionRun(PublicModel):
    x: int
    length: int = Field(ge=1)


class SelectionRow(PublicModel):
    y: int
    runs: list[SelectionRun] = Field(min_length=1)


class EmptySelection(PublicModel):
    kind: Literal["empty"] = "empty"


class AllSelection(PublicModel):
    kind: Literal["all"] = "all"
    rectangle: PositiveRectangle


class MaskSelection(PublicModel):
    kind: Literal["mask"] = "mask"
    bounds: PositiveRectangle
    rows: list[SelectionRow] = Field(min_length=1)


SelectionApplication = Annotated[
    EmptySelection | AllSelection | MaskSelection, Field(discriminator="kind")
]
