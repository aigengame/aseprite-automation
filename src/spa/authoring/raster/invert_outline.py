"""Standalone pixel-only Invert Color and Outline contracts and publication."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, JsonValue, model_validator

from spa.authoring.raster.filter import (
    FILTER_FAILURE_SPECS,
    FILTER_SHARED_RESOURCES,
    ComponentChannels,
    FilterCelEffect,
    FilterCelsTarget,
    FilterImage,
    FilterMutationRequest,
    FilterPaletteBasis,
    FilterTargetObservations,
    publish_filter,
    validate_cel_effects,
)
from spa.contracts.mutation import TargetCommit
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import OperationServices, PackagedHandler, PackagedResource
from spa.contracts.public import (
    CapabilityGap,
    FailureCodeSpec,
    PublicModel,
    RuntimeRequirements,
)
from spa.contracts.raster import (
    RASTER_COLOR_RESOURCE,
    ColorValue,
    ImageContentDigest,
    Point,
    SelectionApplication,
)

Component = Literal["red", "green", "blue", "gray", "alpha"]


class IndexChannels(PublicModel):
    kind: Literal["index"]


PixelFilterChannels = Annotated[
    ComponentChannels[Component] | IndexChannels, Field(discriminator="kind")
]


def _mode_constraints(*, colors: bool = False) -> list[JsonValue]:
    """Project the same mode-specific choices into public JSON Schema."""
    constraints = []
    for mode, names, color_kind in (
        ("rgb", ["red", "green", "blue", "alpha"], "rgba"),
        ("grayscale", ["gray", "alpha"], "grayscale"),
        ("indexed", ["red", "green", "blue", "alpha"], "palette-index"),
    ):
        properties = {
            "channels": {"properties": {"names": {"items": {"enum": names}}}},
            "palette_frame_number": {
                "type": "integer" if mode == "indexed" else "null"
            },
        }
        if mode != "indexed":
            properties["channels"]["properties"]["kind"] = {"const": "components"}
        if colors:
            for field in ("outline_color", "background_color"):
                properties[field] = {"properties": {"kind": {"const": color_kind}}}
        then: dict = {"properties": properties}
        if mode == "indexed":
            then["required"] = ["palette_frame_number"]
        constraints.append(
            {"if": {"properties": {"color_mode": {"const": mode}}}, "then": then}
        )
    return constraints


class PixelFilterRequest(FilterMutationRequest):
    model_config = ConfigDict(json_schema_extra={"allOf": _mode_constraints()})
    color_mode: Literal["rgb", "grayscale", "indexed"]
    channels: PixelFilterChannels
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None
    palette_frame_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def compatible_channels_and_palette(self) -> "PixelFilterRequest":
        if (self.color_mode == "indexed") != (self.palette_frame_number is not None):
            raise ValueError(
                "Indexed pixels require an explicit Palette Frame; other modes omit it"
            )
        if self.channels.kind == "index":
            if self.color_mode != "indexed":
                raise ValueError("Index Channels require Indexed Color Mode")
        elif any(
            name
            not in (
                {"gray", "alpha"}
                if self.color_mode == "grayscale"
                else {"red", "green", "blue", "alpha"}
            )
            for name in self.channels.names
        ):
            raise ValueError("Component Channels must match the Color Mode")
        return self

    def parameters(self) -> dict:
        return self.model_dump(
            exclude_none=True,
            exclude={
                "source_sprite_file",
                "target_sprite_file",
                "in_place",
                "overwrite",
                "aseprite",
                "timeout_seconds",
            },
        )


class InvertColorRequest(PixelFilterRequest):
    """Invert selected components or valid stored Indexes through native Aseprite.

    Tilemap targets and Background Alpha reject before mutation. Indexed index
    processing also validates zero-padded Canvas input against the declared Palette.
    Indexed component quantization does not promise two-pass restoration.
    """


class PresetOutlineMatrix(PublicModel):
    kind: Literal["preset"]
    name: Literal["none", "circle", "square", "horizontal", "vertical"]


class CustomOutlineMatrix(PublicModel):
    kind: Literal["custom"]
    neighbors: list[
        Literal[
            "top-left",
            "top",
            "top-right",
            "left",
            "right",
            "bottom-left",
            "bottom",
            "bottom-right",
        ]
    ] = Field(min_length=1, json_schema_extra={"uniqueItems": True})

    @model_validator(mode="after")
    def unique_neighbors(self) -> "CustomOutlineMatrix":
        if len(set(self.neighbors)) != len(self.neighbors):
            raise ValueError("Outline neighbors must be unique")
        return self


OutlineMatrix = Annotated[
    PresetOutlineMatrix | CustomOutlineMatrix, Field(discriminator="kind")
]


class OutlineRequest(PixelFilterRequest):
    """Native outline of ordinary Cel Images; explicit neighbor positions and colors.

    Selection limits writes, not neighborhood reads. Indexed component Channels
    are a native Capability Gap and reject before mutation. No Palette is edited.
    """

    model_config = ConfigDict(
        json_schema_extra={"allOf": _mode_constraints(colors=True)}
    )
    place: Literal["inside", "outside"]
    outline_color: ColorValue
    background_color: ColorValue
    matrix: OutlineMatrix
    tiled_mode: Literal["none", "x", "y", "both"]

    @model_validator(mode="after")
    def compatible_colors(self) -> "OutlineRequest":
        kind = {"rgb": "rgba", "grayscale": "grayscale", "indexed": "palette-index"}[
            self.color_mode
        ]
        if self.outline_color.kind != kind or self.background_color.kind != kind:
            raise ValueError("Outline Color Values must match the Color Mode")
        return self


class PixelFilterEvidence(
    FilterTargetObservations[
        FilterImage[ImageContentDigest | None], PixelFilterChannels
    ]
):
    cel_effects: list[FilterCelEffect]

    @model_validator(mode="after")
    def consistent_observations(self) -> "PixelFilterEvidence":
        validate_cel_effects(self, self.cel_effects)
        if self.palette_before != self.palette_after:
            raise ValueError("Pixel-only Filters must preserve the Palette")
        if self.processed_image_numbers != [
            image.image_number for image in self.images
        ]:
            raise ValueError("Pixel-only Filter must process every unique target Image")
        return self

    def matches(self, request: PixelFilterRequest) -> bool:
        return (
            self.color_mode == request.color_mode
            and self.channels.kind == request.channels.kind
            and (
                self.channels.kind == "index"
                or (
                    request.channels.kind == "components"
                    and set(self.channels.names) == set(request.channels.names)
                )
            )
            and self.matches_target_selection(request.cels_target, request.selection)
            and (self.palette_basis.frame_number if self.palette_basis else None)
            == request.palette_frame_number
        )


class InvertColorResult(PixelFilterEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa filter invert-color"] = "spa filter invert-color"
    target_commit: TargetCommit


class OutlineEvidence(PixelFilterEvidence):
    place: Literal["inside", "outside"]
    outline_color: ColorValue
    background_color: ColorValue
    matrix: OutlineMatrix
    tiled_mode: Literal["none", "x", "y", "both"]

    def matches_outline(self, request: OutlineRequest) -> bool:
        return self.matches(request) and all(
            getattr(self, name) == getattr(request, name)
            for name in (
                "place",
                "outline_color",
                "background_color",
                "matrix",
                "tiled_mode",
            )
        )


class OutlineResult(OutlineEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa filter outline"] = "spa filter outline"
    target_commit: TargetCommit


class FilterIndexViolation(PublicModel):
    layer_path: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    canvas_position: Point
    source_index: int = Field(ge=0, le=255)
    result_index: int = Field(ge=0, le=255)


class FilterIndexRejection(PublicModel):
    kind: Literal["filter-index"] = "filter-index"
    reason: str
    palette_basis: FilterPaletteBasis
    index_violations: list[FilterIndexViolation] = Field(min_length=1)


INVERT_FAILURE_SPECS = (
    FailureCodeSpec(
        "filter_index_out_of_bounds",
        "Invert Color would use an Index outside the Palette",
        "input",
        FilterIndexRejection,
    ),
)
INVERT_COLOR_RESOURCE = PackagedResource(
    "invert_color", "raster/filter/invert_color.lua"
)
OUTLINE_RESOURCE = PackagedResource("outline", "raster/filter/outline.lua")
INVERT_COLOR_HANDLER = PackagedHandler(
    "invert_color_run",
    "raster/filter/invert_color_run.lua",
    (*FILTER_SHARED_RESOURCES, INVERT_COLOR_RESOURCE),
)
OUTLINE_HANDLER = PackagedHandler(
    "outline_run",
    "raster/filter/outline_run.lua",
    (*FILTER_SHARED_RESOURCES, RASTER_COLOR_RESOURCE, OUTLINE_RESOURCE),
)


def invert_color(
    request: InvertColorRequest, services: OperationServices
) -> InvertColorResult:
    evidence, commit = publish_filter(
        request,
        services,
        INVERT_COLOR_HANDLER,
        lambda _: request.parameters(),
        PixelFilterEvidence,
        lambda evidence: evidence.matches(request),
        (*FILTER_FAILURE_SPECS, *INVERT_FAILURE_SPECS),
    )
    return InvertColorResult(**evidence.model_dump(), target_commit=commit)


def outline(request: OutlineRequest, services: OperationServices) -> OutlineResult:
    evidence, commit = publish_filter(
        request,
        services,
        OUTLINE_HANDLER,
        lambda _: request.parameters(),
        OutlineEvidence,
        lambda evidence: evidence.matches_outline(request),
    )
    return OutlineResult(**evidence.model_dump(), target_commit=commit)


INVERT_OUTLINE_OPERATIONS = (
    OperationDescriptor(
        "filter invert-color",
        InvertColorRequest,
        InvertColorResult,
        invert_color,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=[
                "aseprite_sprite_inspection",
                "aseprite_filter_invert_color",
            ],
        ),
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            *(spec.code for spec in (*FILTER_FAILURE_SPECS, *INVERT_FAILURE_SPECS)),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "filter outline",
        OutlineRequest,
        OutlineResult,
        outline,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=[
                "aseprite_sprite_inspection",
                "aseprite_filter_outline",
            ],
        ),
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            *(spec.code for spec in FILTER_FAILURE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)


def invert_outline_capability_gaps(aseprite_version: str) -> list[CapabilityGap]:
    return [
        CapabilityGap(
            capability=f"spa filter {operation}: Tilemap pixels",
            aseprite_version=aseprite_version,
            evidence="Resolved Tilemap pixel targets are refused before mutation; ordinary Image Layers remain supported.",
        )
        for operation in ("invert-color", "outline")
    ] + [
        CapabilityGap(
            capability="spa filter outline: Indexed component Channels",
            aseprite_version=aseprite_version,
            evidence="On tested baseline Aseprite 1.3.18.5, Indexed component Outline produced no outline while stored Index Channels produced a four-pixel cross. Component execution is refused before mutation; use the explicit Index branch.",
        )
    ]
