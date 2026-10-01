"""Explicit native Filter contracts and staged Brightness/Contrast publication."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.color.palette import (
    EFFECTIVE_PALETTE_RESOURCE,
    PALETTE_SUPPORT_RESOURCE,
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


class GrayscalePixels(PublicModel):
    kind: Literal["pixels"]
    color_mode: Literal["grayscale"]
    channels: ComponentChannels[Literal["gray"]]
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None


class BrightnessContrastRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    brightness: int = Field(ge=-100, le=100)
    contrast: int = Field(ge=-100, le=100)
    application: Annotated[
        RGBPixels | GrayscalePixels, Field(discriminator="color_mode")
    ]

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
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest
    changed: bool


class FilterExclusion(PublicModel):
    layer_path: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)
    reason: str


class FilterEvidence(PublicModel):
    color_mode: Literal["rgb", "grayscale", "indexed"]
    channels: ComponentChannels[Literal["red", "green", "blue", "gray"]]
    requested_intersections: list[FilterCel]
    existing_target_cels: list[FilterCel]
    excluded_layers: list[FilterExclusion]
    images: list[FilterImage]
    affected_cels: list[FilterCel]
    changed: bool
    persisted_reopen_verified: Literal[True]


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
    FILTER_RESOURCE,
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
            },
            request.timeout_seconds,
        )
        rejected = invocation.payload.get("rejection")
        if isinstance(rejected, dict):
            code = rejected.get("code")
            if code in {spec.code for spec in FILTER_FAILURE_SPECS}:
                raise OperationIssue(
                    code,
                    rejected["message"],
                    FilterRejection.model_validate(rejected["details"]),
                )
        try:
            evidence = FilterEvidence.model_validate(invocation.payload)
        except ValueError as exc:
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
