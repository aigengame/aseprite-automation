"""Bounded native Despeckle with explicit pixel targets and Channels."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from spa.authoring.raster.filter import (
    FILTER_FAILURE_SPECS,
    FILTER_SHARED_RESOURCES,
    ComponentChannels,
    FilterCelObservations,
    FilterCelsTarget,
    FilterMutationRequest,
    IndexChannels,
    publish_filter,
)
from spa.authoring.raster.selection_evidence import matches_clipped_selection
from spa.contracts.mutation import TargetCommit
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import OperationServices, PackagedHandler, PackagedResource
from spa.contracts.public import CapabilityGap, PublicModel, RuntimeRequirements
from spa.contracts.raster import Point, SelectionApplication

RGBChannel = Literal["red", "green", "blue", "alpha"]
GrayChannel = Literal["gray", "alpha"]
DespeckleChannel = Literal["red", "green", "blue", "gray", "alpha"]
TiledMode = Literal["none", "x", "y", "both"]


class DespecklePixelTarget[Channels](PublicModel):
    channels: Channels
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None


class RGBDespecklePixels(DespecklePixelTarget[ComponentChannels[RGBChannel]]):
    color_mode: Literal["rgb"]


class GrayscaleDespecklePixels(DespecklePixelTarget[ComponentChannels[GrayChannel]]):
    color_mode: Literal["grayscale"]


class IndexedDespecklePixels(
    DespecklePixelTarget[
        Annotated[
            ComponentChannels[RGBChannel] | IndexChannels, Field(discriminator="kind")
        ]
    ]
):
    color_mode: Literal["indexed"]
    palette_frame_number: int = Field(ge=1)


DespecklePixels = Annotated[
    RGBDespecklePixels | GrayscaleDespecklePixels | IndexedDespecklePixels,
    Field(discriminator="color_mode"),
]


class DespeckleRequest(FilterMutationRequest):
    """Native median over ordinary Cel Images, with explicit dimensions and edges.

    Indexed component Channels use the native RGB Map even for a 1-by-1 window.
    The installed Capability Gaps govern runtime-specific Channel exclusions.
    """

    width: int = Field(ge=1, le=100)
    height: int = Field(ge=1, le=100)
    tiled_mode: TiledMode
    pixels: DespecklePixels


class DespeckleEvidence(
    FilterCelObservations[
        DespeckleChannel,
        Annotated[
            ComponentChannels[DespeckleChannel] | IndexChannels,
            Field(discriminator="kind"),
        ],
    ]
):
    application: Literal["pixels"]
    width: int = Field(ge=1, le=100)
    height: int = Field(ge=1, le=100)
    tiled_mode: TiledMode
    anchor: Point
    sample_count: int = Field(ge=1, le=10000)

    @model_validator(mode="after")
    def consistent_despeckle(self) -> "DespeckleEvidence":
        intersections = {
            (tuple(cel.layer_path), cel.frame_number): cel.image_number
            for cel in self.requested_intersections
        }
        existing = {
            (tuple(cel.layer_path), cel.frame_number): cel.image_number
            for cel in self.existing_target_cels
        }
        if (
            self.application != "pixels"
            or self.palette_indexes
            or self.palette_before != self.palette_after
            or self.sample_count != self.width * self.height
            or self.anchor.x != self.width // 2
            or self.anchor.y != self.height // 2
            or self.processed_image_numbers
            != [image.image_number for image in self.images]
            or len(intersections) != len(self.requested_intersections)
            or len(existing) != len(self.existing_target_cels)
            or existing
            != {
                address: image
                for address, image in intersections.items()
                if image is not None
            }
        ):
            raise ValueError(
                "Despeckle observations disagree with its native pixel path"
            )
        return self

    def _matches_targets(self, target: FilterCelsTarget) -> bool:
        if self.cels_target_kind != target.kind:
            return False
        if target.kind == "all":
            return True
        intersections = [
            (tuple(cel.layer_path), cel.frame_number)
            for cel in self.requested_intersections
        ]
        paths = {path for path, _ in intersections}
        # Names and UUIDs resolve in the Kernel. Paths and Frames are direct facts.
        return (
            not self.excluded_layers
            and len(paths) == len(target.layers)
            and len(intersections) == len(paths) * len(target.frame_numbers)
            and set(intersections)
            == {(path, frame) for path in paths for frame in target.frame_numbers}
            and all(
                tuple(layer.layer_path) in paths
                for layer in target.layers
                if layer.layer_path is not None
            )
        )

    def matches(self, request: DespeckleRequest) -> bool:
        pixels = request.pixels
        channels_match = self.channels.kind == pixels.channels.kind
        if isinstance(self.channels, ComponentChannels):
            channels_match = (
                channels_match
                and isinstance(pixels.channels, ComponentChannels)
                and (set(self.channels.names) == set(pixels.channels.names))
            )
        return (
            channels_match
            and self.color_mode == pixels.color_mode
            and self._matches_targets(pixels.cels_target)
            and matches_clipped_selection(pixels.selection, self.selection)
            and (self.palette_basis.frame_number if self.palette_basis else None)
            == getattr(pixels, "palette_frame_number", None)
            and (self.width, self.height, self.tiled_mode)
            == (request.width, request.height, request.tiled_mode)
        )


class DespeckleResult(DespeckleEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa filter despeckle"] = "spa filter despeckle"
    target_commit: TargetCommit


DESPECKLE_RESOURCE = PackagedResource("despeckle", "raster/filter/despeckle.lua")
DESPECKLE_HANDLER = PackagedHandler(
    "despeckle_run",
    "raster/filter/despeckle_run.lua",
    (*FILTER_SHARED_RESOURCES, DESPECKLE_RESOURCE),
)
DESPECKLE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_filter_despeckle"],
)


def despeckle(
    request: DespeckleRequest, services: OperationServices
) -> DespeckleResult:
    evidence, commit = publish_filter(
        request,
        services,
        DESPECKLE_HANDLER,
        lambda observation: {
            "pixels": request.pixels.model_dump(exclude_none=True),
            "width": request.width,
            "height": request.height,
            "tiled_mode": request.tiled_mode,
        },
        DespeckleEvidence,
        lambda evidence: evidence.matches(request),
    )
    return DespeckleResult(**evidence.model_dump(), target_commit=commit)


def despeckle_capability_gaps(version: str) -> list[CapabilityGap]:
    return [
        CapabilityGap(
            capability="spa filter despeckle: Tilemap pixels",
            aseprite_version=version,
            evidence="Despeckle rejects resolved Tilemap pixel targets before mutation; ordinary Image targets remain independent.",
        ),
        CapabilityGap(
            capability="spa filter despeckle: Indexed components without Green",
            aseprite_version=version,
            evidence="This slice requires Green in Indexed component sets. Native 1.3.18.5 corrupts preserved Green in the excluded sets (issue #39); SPA does not add Channels or substitute Index processing. A later native fix needs focused acceptance before this boundary is extended.",
        ),
    ]


DESPECKLE_OPERATIONS = (
    OperationDescriptor(
        "filter despeckle",
        DespeckleRequest,
        DespeckleResult,
        despeckle,
        lambda result: result.target_commit.target_sprite_file,
        DESPECKLE_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            *(spec.code for spec in FILTER_FAILURE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
