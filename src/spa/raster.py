"""Canonical Raster values shared by authoring and inspection operations."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

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

    @model_validator(mode="after")
    def validate_canonical_runs(self) -> "PixelPatch":
        area = self.rectangle
        previous: PixelRun | None = None
        for run in self.runs:
            if (
                run.y < area.y
                or run.y >= area.y + area.height
                or run.x < area.x
                or run.x + run.length > area.x + area.width
            ):
                raise ValueError("Pixel Patch run is outside its declared Rectangle")
            if previous is not None:
                if run.y < previous.y or (
                    run.y == previous.y and run.x < previous.x + previous.length
                ):
                    raise ValueError(
                        "Pixel Patch runs must be ordered and non-overlapping"
                    )
                if (
                    run.y == previous.y
                    and run.x == previous.x + previous.length
                    and run.color == previous.color
                ):
                    raise ValueError("adjacent equal Pixel Patch runs must be merged")
            previous = run
        return self


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

    @model_validator(mode="after")
    def validate_canonical_mask(self) -> "MaskSelection":
        bounds = self.bounds
        if (
            self.rows[0].y != bounds.y
            or self.rows[-1].y + 1 != bounds.y + bounds.height
        ):
            raise ValueError("Mask Selection bounds are not tight")
        previous_y: int | None = None
        minimum_x: int | None = None
        maximum_x: int | None = None
        for row in self.rows:
            if previous_y is not None and row.y <= previous_y:
                raise ValueError("Mask Selection rows must be ordered and unique")
            if row.y < bounds.y or row.y >= bounds.y + bounds.height:
                raise ValueError("Mask Selection row is outside its bounds")
            previous_end: int | None = None
            for run in row.runs:
                end = run.x + run.length
                if run.x < bounds.x or end > bounds.x + bounds.width:
                    raise ValueError("Mask Selection run is outside its bounds")
                if previous_end is not None and run.x <= previous_end:
                    raise ValueError(
                        "Mask Selection runs must be ordered, non-overlapping, and non-adjacent"
                    )
                previous_end = end
                minimum_x = run.x if minimum_x is None else min(minimum_x, run.x)
                maximum_x = end if maximum_x is None else max(maximum_x, end)
            previous_y = row.y
        if minimum_x != bounds.x or maximum_x != bounds.x + bounds.width:
            raise ValueError("Mask Selection bounds are not tight")
        return self


SelectionApplication = Annotated[
    EmptySelection | AllSelection | MaskSelection, Field(discriminator="kind")
]
