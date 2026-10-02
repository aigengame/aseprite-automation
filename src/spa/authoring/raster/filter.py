"""Explicit native Filter contracts and staged Brightness/Contrast publication."""

from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

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
    RuntimeObservation,
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
    layers: list[LayerAddress] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )
    frame_numbers: list[Annotated[int, Field(ge=1)]] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )

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
    names: list[Channel] = Field(min_length=1, json_schema_extra={"uniqueItems": True})

    @model_validator(mode="after")
    def unique_names(self) -> "ComponentChannels":
        if len(set(self.names)) != len(self.names):
            raise ValueError("Filter Channels must be unique")
        return self


class RGBPixels[Channel = Literal["red", "green", "blue"]](PublicModel):
    kind: Literal["pixels"]
    color_mode: Literal["rgb"]
    channels: ComponentChannels[Channel]
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None


class GrayscalePixels[Channel = Literal["gray"]](PublicModel):
    kind: Literal["pixels"]
    color_mode: Literal["grayscale"]
    channels: ComponentChannels[Channel]
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None


class IndexedPixels[Channel = Literal["red", "green", "blue"]](PublicModel):
    kind: Literal["pixels"]
    color_mode: Literal["indexed"]
    channels: ComponentChannels[Channel]
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None
    palette_frame_number: int = Field(ge=1)


class BrightnessContrastRGBPixels(RGBPixels):
    tileset_mode: Literal["manual"] | None = None


class BrightnessContrastGrayscalePixels(GrayscalePixels):
    tileset_mode: Literal["manual"] | None = None


class BrightnessContrastIndexedPixels(IndexedPixels):
    tileset_mode: Literal["manual"] | None = None


PixelsApplication = Annotated[
    BrightnessContrastRGBPixels
    | BrightnessContrastGrayscalePixels
    | BrightnessContrastIndexedPixels,
    Field(discriminator="color_mode"),
]


class PaletteIndexes(PublicModel):
    indexes: list[Annotated[int, Field(ge=0)]] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )

    @model_validator(mode="after")
    def unique_indexes(self) -> "PaletteIndexes":
        if len(set(self.indexes)) != len(self.indexes):
            raise ValueError("Palette Indexes must be unique")
        return self


class SelectedPaletteEntries(PaletteIndexes):
    kind: Literal["selected"]


class AllPaletteEntries(PublicModel):
    kind: Literal["all"]


class IndexedPaletteEntries[Channel = Literal["red", "green", "blue"]](PublicModel):
    """Edit an exact Palette Change without changing ordinary, Tilemap, or Tile Images."""

    kind: Literal["indexed-palette-entries"]
    palette_frame_number: int = Field(ge=1)
    entries: Annotated[
        AllPaletteEntries | SelectedPaletteEntries, Field(discriminator="kind")
    ]
    channels: ComponentChannels[Channel]


class RGBPaletteColors[Channel = Literal["red", "green", "blue"]](PaletteIndexes):
    kind: Literal["rgb-palette-colors"]
    palette_frame_number: int = Field(ge=1)
    channels: ComponentChannels[Channel]
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None


class BrightnessContrastRGBPaletteColors(RGBPaletteColors):
    tileset_mode: Literal["manual"] | None = None


BrightnessContrastApplication = Annotated[
    PixelsApplication | IndexedPaletteEntries | BrightnessContrastRGBPaletteColors,
    Field(discriminator="kind"),
]


class FilterRequest[Application](RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    application: Application

    _source = field_validator("source_sprite_file")(validate_native_sprite_path)
    _target = field_validator("target_sprite_file")(validate_native_sprite_path)

    @model_validator(mode="after")
    def validate_intent(self) -> "FilterRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class BrightnessContrastRequest(FilterRequest[BrightnessContrastApplication]):
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


class FilterImage[AfterDigest = ImageContentDigest](PublicModel):
    image_number: int = Field(ge=1)
    before_content_digest: ImageContentDigest
    after_content_digest: AfterDigest
    changed: bool


class BrightnessContrastImage(FilterImage):
    image_kind: Literal["ordinary", "tilemap-placement"]


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


class FilterObservations[Image: FilterImage[Any], Channel](PublicModel):
    application: Literal["pixels", "indexed-palette-entries", "rgb-palette-colors"]
    cels_target_kind: Literal["selected", "all"] | None
    selection: SelectionApplication | None
    color_mode: Literal["rgb", "grayscale", "indexed"]
    palette_basis: FilterPaletteBasis | None
    palette_indexes: list[Annotated[int, Field(ge=0)]]
    palette_before: PaletteTimeline
    palette_after: PaletteTimeline
    channels: ComponentChannels[Channel]
    requested_intersections: list[FilterCel]
    existing_target_cels: list[FilterCel]
    excluded_layers: list[FilterExclusion]
    images: list[Image]
    processed_image_numbers: list[Annotated[int, Field(ge=1)]]
    affected_cels: list[FilterCel]
    changed: bool
    persisted_reopen_verified: Literal[True]

    @model_validator(mode="after")
    def consistent_images(self) -> "FilterObservations":
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
        return self

    def matches_application(
        self,
        application: RGBPixels[Any]
        | GrayscalePixels[Any]
        | IndexedPixels[Any]
        | IndexedPaletteEntries[Any]
        | RGBPaletteColors[Any],
    ) -> bool:
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


class FilterEvidence(
    FilterObservations[BrightnessContrastImage, Literal["red", "green", "blue", "gray"]]
):
    brightness: int = Field(ge=-100, le=100)
    contrast: int = Field(ge=-100, le=100)
    requested_tileset_mode: Literal["manual"] | None
    observed_tileset_mode: Literal["manual"] | None
    changed_tiles: list[FilterTileChange]

    @model_validator(mode="after")
    def consistent_observations(self) -> "FilterEvidence":
        numbers = [image.image_number for image in self.images]
        for image in self.images:
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
        direct = {
            (tuple(cel.layer_path), cel.frame_number)
            for cel in self.existing_target_cels
        }
        affected = {
            (tuple(cel.layer_path), cel.frame_number): cel.image_number
            for cel in self.affected_cels
        }
        image_uses = Counter(affected.values())
        for tile in self.changed_tiles:
            seen = set()
            for cel in tile.referencing_cels:
                key = (tuple(cel.layer_path), cel.frame_number)
                reasons = set(cel.relationships)
                shared_image = (
                    cel.image_number is not None and image_uses[cel.image_number] > 1
                )
                if (
                    key in seen
                    or len(reasons) != len(cel.relationships)
                    or "shared-tile" not in reasons
                    or ("direct-target" in reasons) != (key in direct)
                    or ("shared-cel-image" in reasons) != shared_image
                    or cel.image_number != affected.get(key)
                    or (
                        cel.image_number is not None
                        and (
                            cel.image_number not in numbers
                            or self.images[cel.image_number - 1].image_kind
                            != "tilemap-placement"
                        )
                    )
                ):
                    raise ValueError(
                        "Tile references disagree with Filter Cel Image targets"
                    )
                seen.add(key)
            if not seen & direct:
                raise ValueError("Changed Tile has no direct target reference")
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
        return (
            self.matches_application(request.application)
            and self.brightness == request.brightness
            and self.contrast == request.contrast
            and self.requested_tileset_mode
            == getattr(request.application, "tileset_mode", None)
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
FILTER_SHARED_RESOURCES = (
    *SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    DIGEST_RESOURCE,
    EFFECTIVE_PALETTE_RESOURCE,
    PALETTE_SUPPORT_RESOURCE,
    SELECTION_MASK_RESOURCE,
    PALETTE_IMAGES_RESOURCE,
    FILTER_RESOURCE,
    FILTER_TILES_RESOURCE,
    PackagedResource("filter_application", "raster/filter/filter_application.lua"),
    PackagedResource("filter_run", "raster/filter/filter_run.lua"),
)
FILTER_RESOURCES = (
    *FILTER_SHARED_RESOURCES,
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
    gaps = []
    if (
        "aseprite_filter_brightness_contrast_tilemap_manual"
        not in verified_capabilities
    ):
        gaps.append(
            CapabilityGap(
                capability="spa filter brightness-contrast: Manual Tilemap pixels",
                aseprite_version=aseprite_version,
                evidence=(
                    "The selected runtime did not pass the Manual Tilemap Filter probe. "
                    "Requests with actual Tilemap pixel targets are refused before mutation. "
                    "Ordinary Image and Indexed Palette-only application remain independent."
                ),
            )
        )
    gaps.append(
        CapabilityGap(
            capability="spa filter hue-saturation: Tilemap pixels",
            aseprite_version=aseprite_version,
            evidence=(
                "Hue/Saturation currently rejects resolved Tilemap pixel targets. "
                "Ordinary Image and Indexed Palette-only applications remain supported."
            ),
        )
    )
    return gaps


def publish_filter[Evidence: PublicModel](
    request: FilterRequest,
    services: OperationServices,
    handler: PackagedHandler,
    parameters: Callable[[RuntimeObservation], dict[str, Any]],
    evidence_type: type[Evidence],
    matches: Callable[[Evidence], bool],
) -> tuple[Evidence, TargetCommit]:
    """Publish only after native persistence and request-matched evidence succeed."""
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
            handler,
            {
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(mutation.staged_sprite_file),
                "application": request.application.model_dump(exclude_none=True),
                **parameters(observation),
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
            evidence = evidence_type.model_validate(invocation.payload)
            if not matches(evidence):
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
        return evidence, mutation.commit()


def brightness_contrast(
    request: BrightnessContrastRequest, services: OperationServices
) -> BrightnessContrastResult:
    evidence, commit = publish_filter(
        request,
        services,
        BRIGHTNESS_CONTRAST_HANDLER,
        lambda observation: {
            "brightness": request.brightness,
            "contrast": request.contrast,
            "tilemap_manual_filter_available": (
                "aseprite_filter_brightness_contrast_tilemap_manual"
                in observation.verified_capabilities
            ),
        },
        FilterEvidence,
        lambda evidence: evidence.matches(request),
    )
    return BrightnessContrastResult(**evidence.model_dump(), target_commit=commit)


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
