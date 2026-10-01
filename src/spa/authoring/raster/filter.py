"""Explicit native Filter contracts and staged Brightness/Contrast publication."""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.color.palette import (
    EFFECTIVE_PALETTE_RESOURCE,
    PALETTE_IMAGES_RESOURCE,
    PALETTE_SUPPORT_RESOURCE,
    PaletteTimeline,
)
from spa.authoring.document.layer import LayerAddress
from spa.authoring.document.sprite import (
    SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
)
from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    validate_native_sprite_path,
)
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import (
    CapabilityGap,
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.contracts.raster import (
    SELECTION_MASK_RESOURCE,
    ImageContentDigest,
    SelectionApplication,
)


class SelectedFilterCels(PublicModel):
    """Exact Layer/Frame Cartesian product; non-editable Layers reject the whole operation."""

    kind: Literal["selected"]
    layers: list[LayerAddress] = Field(min_length=1)
    frame_numbers: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_choices(self) -> "SelectedFilterCels":
        if len(set(self.frame_numbers)) != len(self.frame_numbers):
            raise ValueError("Filter Frame numbers must be unique")
        if len({layer.model_dump_json() for layer in self.layers}) != len(self.layers):
            raise ValueError("Filter Layer addresses must be unique")
        return self


class AllFilterCels(PublicModel):
    kind: Literal["all"]


FilterCelsTarget = Annotated[
    SelectedFilterCels | AllFilterCels, Field(discriminator="kind")
]


class ComponentChannels[Channel](PublicModel):
    kind: Literal["components"]
    names: list[Channel] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_names(self) -> "ComponentChannels":
        if len(set(self.names)) != len(self.names):
            raise ValueError("Filter Channels must be unique")
        return self


class RGBPixels(PublicModel):
    kind: Literal["pixels"]
    color_mode: Literal["rgb"]
    channels: ComponentChannels[Literal["red", "green", "blue"]]
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None
    tileset_mode: Literal["manual"] | None = None


class GrayscalePixels(PublicModel):
    kind: Literal["pixels"]
    color_mode: Literal["grayscale"]
    channels: ComponentChannels[Literal["gray"]]
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None
    tileset_mode: Literal["manual"] | None = None


class IndexedPixels(PublicModel):
    kind: Literal["pixels"]
    color_mode: Literal["indexed"]
    channels: ComponentChannels[Literal["red", "green", "blue"]]
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None
    tileset_mode: Literal["manual"] | None = None
    palette_frame_number: int = Field(ge=1)


PixelsApplication = Annotated[
    RGBPixels | GrayscalePixels | IndexedPixels, Field(discriminator="color_mode")
]


class PaletteIndexes(PublicModel):
    indexes: list[Annotated[int, Field(ge=0)]] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_indexes(self) -> "PaletteIndexes":
        if len(set(self.indexes)) != len(self.indexes):
            raise ValueError("Palette Indexes must be unique")
        return self


class SelectedPaletteEntries(PaletteIndexes):
    kind: Literal["selected"]


class AllPaletteEntries(PublicModel):
    kind: Literal["all"]


class IndexedPaletteEntries(PublicModel):
    """Edit an exact Palette Change without changing ordinary, Tilemap, or Tile Images."""

    kind: Literal["indexed-palette-entries"]
    palette_frame_number: int = Field(ge=1)
    entries: Annotated[
        AllPaletteEntries | SelectedPaletteEntries, Field(discriminator="kind")
    ]
    channels: ComponentChannels[Literal["red", "green", "blue"]]


class RGBPaletteColors(PaletteIndexes):
    kind: Literal["rgb-palette-colors"]
    palette_frame_number: int = Field(ge=1)
    channels: ComponentChannels[Literal["red", "green", "blue"]]
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None
    tileset_mode: Literal["manual"] | None = None


BrightnessContrastApplication = Annotated[
    PixelsApplication | IndexedPaletteEntries | RGBPaletteColors,
    Field(discriminator="kind"),
]


class BrightnessContrastRequest(RuntimeRequest):
    """Native Brightness/Contrast with explicit Channels and application.

    Pixel applications require explicit tileset_mode=manual for Tilemap targets.
    Selection limits direct Canvas application; shared Tiles can change outside
    that Selection and target set. Distinct target Cel Images can filter a shared
    Tile more than once. Indexed Palette-only application has no Tileset Mode.
    RGB/Gray pixel and Palette Entry Alpha are preserved; Indexed pixel RGB Map
    quantization may choose an Entry with different Alpha. Explicit 0/0 is a no-op.
    """

    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    brightness: int = Field(ge=-100, le=100)
    contrast: int = Field(ge=-100, le=100)
    application: BrightnessContrastApplication

    _source = field_validator("source_sprite_file")(validate_native_sprite_path)
    _target = field_validator("target_sprite_file")(validate_native_sprite_path)

    @model_validator(mode="after")
    def validate_intent(self) -> "BrightnessContrastRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class FilterCel(PublicModel):
    layer_path: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    image_number: int | None = Field(ge=1)


class FilterImage(PublicModel):
    image_number: int = Field(ge=1)
    image_kind: Literal["ordinary", "tilemap-placement"]
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest
    changed: bool


class FilterTileReference(FilterCel):
    """A Cel references a changed Tile; this is not a rendered-change measurement."""

    relationships: list[Literal["direct-target", "shared-cel-image", "shared-tile"]] = (
        Field(min_length=1)
    )


class FilterTileChange(PublicModel):
    """Current Tile address and bitmap change, without a once-per-Tile promise."""

    tileset_index: int = Field(ge=1)
    tile_index: int = Field(ge=1)
    tile_key: str | None
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest
    referencing_cels: list[FilterTileReference] = Field(min_length=1)


class FilterExclusion(PublicModel):
    layer_path: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)
    reason: str


class FilterPaletteBasis(PublicModel):
    frame_number: int = Field(ge=1)
    palette_frame_number: int = Field(ge=1)
    palette_size: int = Field(ge=1)


class FilterEvidence(PublicModel):
    brightness: int = Field(ge=-100, le=100)
    contrast: int = Field(ge=-100, le=100)
    application: Literal["pixels", "indexed-palette-entries", "rgb-palette-colors"]
    cels_target_kind: Literal["selected", "all"] | None
    selection: SelectionApplication | None
    color_mode: Literal["rgb", "grayscale", "indexed"]
    palette_basis: FilterPaletteBasis | None
    palette_indexes: list[Annotated[int, Field(ge=0)]]
    palette_before: PaletteTimeline
    palette_after: PaletteTimeline
    channels: ComponentChannels[Literal["red", "green", "blue", "gray"]]
    requested_intersections: list[FilterCel]
    existing_target_cels: list[FilterCel]
    excluded_layers: list[FilterExclusion]
    images: list[FilterImage]
    requested_tileset_mode: Literal["manual"] | None
    observed_tileset_mode: Literal["manual"] | None
    changed_tiles: list[FilterTileChange]
    processed_image_numbers: list[Annotated[int, Field(ge=1)]]
    affected_cels: list[FilterCel]
    changed: bool
    persisted_reopen_verified: Literal[True]

    @model_validator(mode="after")
    def consistent_observations(self) -> "FilterEvidence":
        numbers = [image.image_number for image in self.images]
        if numbers != list(range(1, len(self.images) + 1)):
            raise ValueError("Filter Images must have consecutive unique numbers")
        for image in self.images:
            if image.changed != (
                image.before_content_digest != image.after_content_digest
            ):
                raise ValueError(
                    "Filter Image change disagrees with its content digests"
                )
            if image.image_kind == "tilemap-placement" and image.changed:
                raise ValueError("Manual Filter must preserve Tilemap placement Images")
        tilemaps = any(image.image_kind == "tilemap-placement" for image in self.images)
        if (self.observed_tileset_mode == "manual") != tilemaps or (
            tilemaps and self.requested_tileset_mode != "manual"
        ):
            raise ValueError(
                "Tilemap Filter requires requested and observed Manual mode"
            )
        if self.changed_tiles and not tilemaps:
            raise ValueError("Tile bitmap changes require Tilemap targets")
        addresses = [
            (tile.tileset_index, tile.tile_index) for tile in self.changed_tiles
        ]
        if len(set(addresses)) != len(addresses) or any(
            tile.before_content_digest == tile.after_content_digest
            for tile in self.changed_tiles
        ):
            raise ValueError(
                "Changed Tiles must have unique addresses and different digests"
            )
        if self.changed != (
            any(image.changed for image in self.images)
            or bool(self.changed_tiles)
            or self.palette_before != self.palette_after
        ):
            raise ValueError(
                "Filter change disagrees with observed Images and Palettes"
            )
        noop = self.brightness == self.contrast == 0
        if self.processed_image_numbers != ([] if noop else numbers) or (
            noop and self.changed
        ):
            raise ValueError("Filter processing disagrees with the declared adjustment")
        return self

    def matches(self, request: BrightnessContrastRequest) -> bool:
        application = request.application
        palette_only = isinstance(application, IndexedPaletteEntries)
        mode = (
            "indexed"
            if palette_only
            else (
                "rgb"
                if isinstance(application, RGBPaletteColors)
                else application.color_mode
            )
        )
        frame = getattr(application, "palette_frame_number", None)
        if palette_only:
            indexes = (
                list(range(self.palette_basis.palette_size))
                if application.entries.kind == "all" and self.palette_basis
                else getattr(application.entries, "indexes", [])
            )
        else:
            indexes = (
                application.indexes if isinstance(application, RGBPaletteColors) else []
            )
        return (
            self.application == application.kind
            and self.color_mode == mode
            and self.brightness == request.brightness
            and self.contrast == request.contrast
            and self.requested_tileset_mode
            == getattr(application, "tileset_mode", None)
            and set(self.channels.names) == set(application.channels.names)
            and self.cels_target_kind
            == (None if palette_only else application.cels_target.kind)
            and (self.selection is None) == palette_only
            and (self.palette_basis.frame_number if self.palette_basis else None)
            == frame
            and self.palette_indexes == sorted(indexes)
            and (not palette_only or not (self.images or self.existing_target_cels))
            and (
                self.application != "pixels"
                or self.palette_before == self.palette_after
            )
        )


class BrightnessContrastResult(FilterEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa filter brightness-contrast"] = (
        "spa filter brightness-contrast"
    )
    target_commit: TargetCommit


class FilterRejection(PublicModel):
    kind: Literal["filter"] = "filter"
    reason: str


FILTER_FAILURE_SPECS = (
    FailureCodeSpec(
        "filter_invalid_target",
        "Filter targets cannot be resolved or edited",
        "input",
        FilterRejection,
    ),
    FailureCodeSpec(
        "filter_unsupported_document",
        "The document cannot use the requested native Filter path",
        "input",
        FilterRejection,
    ),
)
FILTER_RESOURCE = PackagedResource("filter_support", "raster/filter/filter_support.lua")
FILTER_TILES_RESOURCE = PackagedResource(
    "filter_tiles", "raster/filter/filter_tiles.lua"
)
BRIGHTNESS_CONTRAST_RESOURCE = PackagedResource(
    "brightness_contrast", "raster/filter/brightness_contrast.lua"
)
FILTER_RESOURCES = (
    *SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    DIGEST_RESOURCE,
    EFFECTIVE_PALETTE_RESOURCE,
    PALETTE_SUPPORT_RESOURCE,
    SELECTION_MASK_RESOURCE,
    PALETTE_IMAGES_RESOURCE,
    FILTER_RESOURCE,
    FILTER_TILES_RESOURCE,
    BRIGHTNESS_CONTRAST_RESOURCE,
)
BRIGHTNESS_CONTRAST_HANDLER = PackagedHandler(
    "brightness_contrast_run",
    "raster/filter/brightness_contrast_run.lua",
    FILTER_RESOURCES,
)
FILTER_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_sprite_inspection",
        "aseprite_filter_brightness_contrast",
    ],
)


def filter_capability_gaps(
    aseprite_version: str, verified_capabilities: Sequence[str]
) -> list[CapabilityGap]:
    if "aseprite_filter_brightness_contrast_tilemap_manual" in verified_capabilities:
        return []
    return [
        CapabilityGap(
            capability="spa filter brightness-contrast: Manual Tilemap pixels",
            aseprite_version=aseprite_version,
            evidence=(
                "The selected runtime did not pass the Manual Tilemap Filter probe. "
                "Requests with actual Tilemap pixel targets are refused before mutation. "
                "Ordinary Image and Indexed Palette-only application remain independent."
            ),
        )
    ]


def brightness_contrast(
    request: BrightnessContrastRequest, services: OperationServices
) -> BrightnessContrastResult:
    completion = prepare_mutation(
        services.target_files,
        Path(request.source_sprite_file),
        Path(request.target_sprite_file),
        in_place=request.in_place,
        overwrite=request.overwrite,
        identity_change_message="Source/Target publication identity changed before Target Commit",
    )
    observation = services.probe_runtime(request)
    with completion as mutation:
        invocation = services.invoke_kernel(
            observation,
            BRIGHTNESS_CONTRAST_HANDLER,
            {
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(mutation.staged_sprite_file),
                "application": request.application.model_dump(exclude_none=True),
                "brightness": request.brightness,
                "contrast": request.contrast,
                "tilemap_manual_filter_available": (
                    "aseprite_filter_brightness_contrast_tilemap_manual"
                    in observation.verified_capabilities
                ),
            },
            request.timeout_seconds,
        )
        try:
            rejected = invocation.payload.get("rejection")
            if rejected is not None:
                code = rejected["code"]
                message = rejected["message"]
                details = FilterRejection.model_validate(rejected["details"])
                if code not in {
                    spec.code for spec in FILTER_FAILURE_SPECS
                } or not isinstance(message, str):
                    raise ValueError("Invalid Filter rejection")
                raise OperationIssue(
                    code,
                    message,
                    details,
                )
            evidence = FilterEvidence.model_validate(invocation.payload)
            if not evidence.matches(request):
                raise ValueError(
                    "Filter evidence disagrees with the requested application"
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Invalid persisted Filter evidence",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        return BrightnessContrastResult(
            **evidence.model_dump(), target_commit=mutation.commit()
        )


FILTER_OPERATIONS = (
    OperationDescriptor(
        "filter brightness-contrast",
        BrightnessContrastRequest,
        BrightnessContrastResult,
        brightness_contrast,
        lambda result: result.target_commit.target_sprite_file,
        FILTER_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            *(spec.code for spec in FILTER_FAILURE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
