"""Native Replace Color matching and observed stored-pixel changes."""

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from spa.authoring.raster.filter import (
    FILTER_FAILURE_SPECS,
    FILTER_SHARED_RESOURCES,
    publish_filter,
)
from spa.authoring.raster.pixel_filter import (
    PixelFilterEvidence,
    PixelFilterRequest,
    pixel_mode_schema,
)
from spa.contracts.mutation import TargetCommit
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import OperationServices, PackagedHandler, PackagedResource
from spa.contracts.public import RuntimeRequirements
from spa.contracts.raster import ColorValue


def _replace_schema() -> dict:
    schema = pixel_mode_schema()
    schema["allOf"].extend(
        {
            "if": {"properties": {"color_mode": {"const": mode}}},
            "then": {
                "properties": {
                    name: {"properties": {"kind": {"const": kind}}}
                    for name in ("from", "to")
                }
            },
        }
        for mode, kind in (
            ("rgb", "rgba"),
            ("grayscale", "grayscale"),
            ("indexed", "palette-index"),
        )
    )
    return schema


class ReplaceColorRequest(PixelFilterRequest):
    """Replace native component/index matches within explicit pixel targets.

    Tolerance is inclusive on each selected component, or on stored Index distance.
    Indexed inputs are PaletteIndex Color Values in both Channel modes. Equal
    input colors are valid; positive tolerance can still change nearby pixels.
    """

    model_config = ConfigDict(
        serialize_by_alias=True, json_schema_extra=_replace_schema()
    )
    from_color: ColorValue = Field(alias="from")
    to: ColorValue
    tolerance: int = Field(ge=0, le=255)

    @model_validator(mode="after")
    def applicable_colors(self) -> "ReplaceColorRequest":
        kind = {"rgb": "rgba", "grayscale": "grayscale", "indexed": "palette-index"}[
            self.color_mode
        ]
        if self.from_color.kind != kind or self.to.kind != kind:
            raise ValueError(
                "From and To Color Values must match the requested Color Mode"
            )
        return self


class ReplaceColorEvidence(PixelFilterEvidence):
    model_config = ConfigDict(serialize_by_alias=True)
    from_color: ColorValue = Field(alias="from")
    to: ColorValue
    tolerance: int = Field(ge=0, le=255)
    changed_pixel_count: int = Field(ge=0)

    @model_validator(mode="after")
    def consistent_pixel_count(self) -> "ReplaceColorEvidence":
        # One original Image is counted once, even when several Cels share it.
        areas = {}
        for effect in self.cel_effects:
            before, after = effect.before, effect.after
            area = before.width * before.height
            if after is not None:
                width = max(before.x + before.width, after.x + after.width) - min(
                    before.x, after.x
                )
                height = max(before.y + before.height, after.y + after.height) - min(
                    before.y, after.y
                )
                area = width * height
            areas[effect.image_number] = max(areas.get(effect.image_number, 0), area)
        if self.changed_pixel_count > sum(areas.values()) or (
            self.changed_pixel_count > 0 and not self.changed
        ):
            raise ValueError(
                "Changed pixel count disagrees with observed native writeback"
            )
        return self


class ReplaceColorResult(ReplaceColorEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa filter replace-color"] = "spa filter replace-color"
    target_commit: TargetCommit


REPLACE_COLOR_RESOURCE = PackagedResource(
    "replace_color", "raster/filter/replace_color.lua"
)
REPLACE_COLOR_HANDLER = PackagedHandler(
    "replace_color_run",
    "raster/filter/replace_color_run.lua",
    (*FILTER_SHARED_RESOURCES, REPLACE_COLOR_RESOURCE),
)
REPLACE_COLOR_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_sprite_inspection",
        "aseprite_filter_replace_color",
    ],
)


def replace_color(
    request: ReplaceColorRequest, services: OperationServices
) -> ReplaceColorResult:
    evidence, commit = publish_filter(
        request,
        services,
        REPLACE_COLOR_HANDLER,
        lambda _: {
            **request.pixel_parameters(),
            "from": request.from_color.model_dump(),
            "to": request.to.model_dump(),
            "tolerance": request.tolerance,
        },
        ReplaceColorEvidence,
        lambda evidence: (
            evidence.matches_pixels(request)
            and evidence.from_color == request.from_color
            and evidence.to == request.to
            and evidence.tolerance == request.tolerance
        ),
    )
    return ReplaceColorResult(**evidence.model_dump(), target_commit=commit)


REPLACE_COLOR_OPERATIONS = (
    OperationDescriptor(
        "filter replace-color",
        ReplaceColorRequest,
        ReplaceColorResult,
        replace_color,
        lambda result: result.target_commit.target_sprite_file,
        REPLACE_COLOR_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            *(spec.code for spec in FILTER_FAILURE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
