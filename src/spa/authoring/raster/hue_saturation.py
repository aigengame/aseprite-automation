"""Native Hue/Saturation adjustment forms and verified Target publication."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from spa.authoring.raster.filter import (
    FILTER_FAILURE_SPECS,
    FILTER_SHARED_RESOURCES,
    FilterCelObservations,
    FilterRequest,
    GrayscalePixels,
    IndexedPaletteEntries,
    IndexedPixels,
    RGBPaletteColors,
    RGBPixels,
    publish_filter,
)
from spa.contracts.mutation import TargetCommit
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    OperationServices,
    PackagedHandler,
    PackagedResource,
)
from spa.contracts.public import PublicModel, RuntimeRequirements

RGBChannel = Literal["red", "green", "blue", "alpha"]
GrayChannel = Literal["gray", "alpha"]
HueApplication = Annotated[
    Annotated[
        RGBPixels[RGBChannel]
        | GrayscalePixels[GrayChannel]
        | IndexedPixels[RGBChannel],
        Field(discriminator="color_mode"),
    ]
    | IndexedPaletteEntries[RGBChannel]
    | RGBPaletteColors[RGBChannel],
    Field(discriminator="kind"),
]


class HSLAdjustment(PublicModel):
    mode: Literal["hsl-multiply", "hsl-add"]
    hue: int = Field(ge=-180, le=180)
    saturation: int = Field(ge=-100, le=100)
    lightness: int = Field(ge=-100, le=100)


class HSVAdjustment(PublicModel):
    mode: Literal["hsv-multiply", "hsv-add"]
    hue: int = Field(ge=-180, le=180)
    saturation: int = Field(ge=-100, le=100)
    value: int = Field(ge=-100, le=100)


class GrayAdjustment(PublicModel):
    mode: Literal["grayscale"]
    lightness: int = Field(ge=-100, le=100)


HueAdjustment = Annotated[
    HSLAdjustment | HSVAdjustment | GrayAdjustment, Field(discriminator="mode")
]


def _channel_condition(names: list[str]) -> dict:
    return {
        "properties": {
            "application": {
                "properties": {
                    "channels": {"properties": {"names": {"contains": {"enum": names}}}}
                }
            }
        }
    }


class HueSaturationRequest(FilterRequest[HueApplication]):
    """Native HSL/HSV color adjustment and independent Alpha multiplication.

    Every selected Channel has exactly its applicable parameters. All-zero is an
    observable no-op. Pixel targets are ordinary Image Layers; Tilemap pixels and
    Background Alpha reject before mutation. Palette-only needs no Cel target.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": _channel_condition(["red", "green", "blue", "gray"]),
                    "then": {
                        "required": ["adjustment"],
                        "properties": {"adjustment": {"type": "object"}},
                    },
                    "else": {"properties": {"adjustment": {"type": "null"}}},
                },
                {
                    "if": _channel_condition(["gray"]),
                    "then": {
                        "properties": {
                            "adjustment": {
                                "properties": {"mode": {"const": "grayscale"}}
                            }
                        }
                    },
                    "else": {
                        "properties": {
                            "adjustment": {
                                "properties": {"mode": {"not": {"const": "grayscale"}}}
                            }
                        }
                    },
                },
                {
                    "if": _channel_condition(["alpha"]),
                    "then": {
                        "required": ["alpha"],
                        "properties": {"alpha": {"type": "integer"}},
                    },
                    "else": {"properties": {"alpha": {"type": "null"}}},
                },
            ]
        }
    )
    adjustment: HueAdjustment | None = None
    alpha: int | None = Field(default=None, ge=-100, le=100)

    @model_validator(mode="after")
    def applicable_adjustments(self) -> "HueSaturationRequest":
        names = self.application.channels.names
        color = any(name != "alpha" for name in names)
        if color != (self.adjustment is not None):
            raise ValueError(
                "Color adjustment is required exactly when a color Channel is selected"
            )
        if self.adjustment is not None and (
            ("gray" in names) != (self.adjustment.mode == "grayscale")
        ):
            raise ValueError("Adjustment mode must match the selected color Channels")
        if ("alpha" in names) != (self.alpha is not None):
            raise ValueError(
                "Alpha adjustment is required exactly when Alpha Channel is selected"
            )
        return self


def is_noop(adjustment: HueAdjustment | None, alpha: int | None) -> bool:
    return not alpha and (
        adjustment is None or not any(adjustment.model_dump(exclude={"mode"}).values())
    )


class HueSaturationEvidence(
    FilterCelObservations[Literal["red", "green", "blue", "gray", "alpha"]]
):
    adjustment: HueAdjustment | None
    alpha: int | None = Field(ge=-100, le=100)

    @model_validator(mode="after")
    def consistent_observations(self) -> "HueSaturationEvidence":
        numbers = [image.image_number for image in self.images]
        noop = is_noop(self.adjustment, self.alpha)
        if self.processed_image_numbers != ([] if noop else numbers) or (
            noop and self.changed
        ):
            raise ValueError("Filter processing disagrees with the declared adjustment")
        return self

    def matches(self, request: HueSaturationRequest) -> bool:
        return (
            self.matches_application(request.application)
            and self.adjustment == request.adjustment
            and self.alpha == request.alpha
        )


class HueSaturationResult(HueSaturationEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa filter hue-saturation"] = "spa filter hue-saturation"
    target_commit: TargetCommit


HUE_SATURATION_RESOURCE = PackagedResource(
    "hue_saturation", "raster/filter/hue_saturation.lua"
)
HUE_SATURATION_HANDLER = PackagedHandler(
    "hue_saturation_run",
    "raster/filter/hue_saturation_run.lua",
    (*FILTER_SHARED_RESOURCES, HUE_SATURATION_RESOURCE),
)
HUE_SATURATION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_sprite_inspection",
        "aseprite_filter_hue_saturation",
    ],
)


def hue_saturation(
    request: HueSaturationRequest, services: OperationServices
) -> HueSaturationResult:
    evidence, commit = publish_filter(
        request,
        services,
        HUE_SATURATION_HANDLER,
        lambda _observation: {
            "application": request.application.model_dump(exclude_none=True),
            "adjustment": request.adjustment.model_dump()
            if request.adjustment
            else None,
            "alpha": request.alpha,
        },
        HueSaturationEvidence,
        lambda evidence: evidence.matches(request),
    )
    return HueSaturationResult(**evidence.model_dump(), target_commit=commit)


HUE_SATURATION_OPERATIONS = (
    OperationDescriptor(
        "filter hue-saturation",
        HueSaturationRequest,
        HueSaturationResult,
        hue_saturation,
        lambda result: result.target_commit.target_sprite_file,
        HUE_SATURATION_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            *(spec.code for spec in FILTER_FAILURE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
