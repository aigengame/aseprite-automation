"""Native linear Color Curve with ordered byte-domain control points."""

from typing import Literal

from pydantic import Field, model_validator

from spa.authoring.raster.filter import (
    FILTER_FAILURE_SPECS,
    FILTER_SHARED_RESOURCES,
    publish_filter,
)
from spa.authoring.raster.pixel_filter import PixelFilterEvidence, PixelFilterRequest
from spa.contracts.mutation import TargetCommit
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import OperationServices, PackagedHandler, PackagedResource
from spa.contracts.public import PublicModel, RuntimeRequirements


class CurvePoint(PublicModel):
    input: int = Field(ge=0, le=255)
    output: int = Field(ge=0, le=255)


class ColorCurveRequest(PixelFilterRequest):
    """Apply one native linear curve to explicit pixel Channels.

    Inputs must strictly increase. One point is a constant curve; native endpoint
    extension supplies omitted endpoints. Tilemap pixels and Background Alpha
    are currently refused. The operation does not mutate Palettes.
    """

    points: list[CurvePoint] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def ordered_points(self) -> "ColorCurveRequest":
        if any(a.input >= b.input for a, b in zip(self.points, self.points[1:])):
            raise ValueError("Curve point inputs must strictly increase")
        return self


class ColorCurveEvidence(PixelFilterEvidence):
    points: list[CurvePoint] = Field(min_length=1, max_length=256)


class ColorCurveResult(ColorCurveEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa filter color-curve"] = "spa filter color-curve"
    target_commit: TargetCommit


COLOR_CURVE_RESOURCE = PackagedResource("color_curve", "raster/filter/color_curve.lua")
COLOR_CURVE_HANDLER = PackagedHandler(
    "color_curve_run",
    "raster/filter/color_curve_run.lua",
    (*FILTER_SHARED_RESOURCES, COLOR_CURVE_RESOURCE),
)
COLOR_CURVE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_filter_color_curve"],
)


def color_curve(
    request: ColorCurveRequest, services: OperationServices
) -> ColorCurveResult:
    evidence, commit = publish_filter(
        request,
        services,
        COLOR_CURVE_HANDLER,
        lambda _: {
            **request.pixel_parameters(),
            "points": [point.model_dump() for point in request.points],
        },
        ColorCurveEvidence,
        lambda evidence: (
            evidence.matches_pixels(request) and evidence.points == request.points
        ),
    )
    return ColorCurveResult(**evidence.model_dump(), target_commit=commit)


COLOR_CURVE_OPERATIONS = (
    OperationDescriptor(
        "filter color-curve",
        ColorCurveRequest,
        ColorCurveResult,
        color_curve,
        lambda result: result.target_commit.target_sprite_file,
        COLOR_CURVE_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            *(spec.code for spec in FILTER_FAILURE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
