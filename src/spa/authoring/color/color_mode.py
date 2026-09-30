"""Explicit native Color Mode paths and complete conversion evidence."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.color.palette import (
    EFFECTIVE_PALETTE_RESOURCE,
    PALETTE_SUPPORT_RESOURCE,
    PaletteTimeline,
)
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
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import PublicModel, RuntimeRequest, RuntimeRequirements

ColorMode = Literal["rgb", "grayscale", "indexed"]
RGBMapAlgorithm = Literal["default", "rgb5a3", "octree"]
ColorBestFitCriteria = Literal["default", "rgb", "linearizedRGB", "ciexyz", "cielab"]
ToGray = Literal["luma", "hsv", "hsl"]


class InstalledMatrix(PublicModel):
    kind: Literal["installed"]
    id: str = Field(min_length=1)


class FileMatrix(PublicModel):
    kind: Literal["file"]
    path: str = Field(min_length=1)


Matrix = Annotated[InstalledMatrix | FileMatrix, Field(discriminator="kind")]


class NoDithering(PublicModel):
    algorithm: Literal["none"]


class MatrixDithering(PublicModel):
    algorithm: Literal["ordered", "old"]
    matrix: Matrix | None = None


class ErrorDiffusion(PublicModel):
    algorithm: Literal["error-diffusion"]
    dithering_factor: float = Field(ge=0, le=1, allow_inf_nan=False)


Dithering = Annotated[
    NoDithering | MatrixDithering | ErrorDiffusion, Field(discriminator="algorithm")
]


class RGBTarget(PublicModel):
    color_mode: Literal["rgb"]


class GrayscaleNoOp(PublicModel):
    color_mode: Literal["grayscale"]


class IndexedNoOp(PublicModel):
    color_mode: Literal["indexed"]


class GrayscaleTarget(PublicModel):
    color_mode: Literal["grayscale"]
    to_gray: ToGray


class IndexedTarget(PublicModel):
    color_mode: Literal["indexed"]
    rgb_map_algorithm: RGBMapAlgorithm
    color_best_fit_criteria: ColorBestFitCriteria


class DitheredIndexedTarget(IndexedTarget):
    dithering: Dithering


class FromRGB(PublicModel):
    source_color_mode: Literal["rgb"]
    target: Annotated[
        RGBTarget | GrayscaleTarget | DitheredIndexedTarget,
        Field(discriminator="color_mode"),
    ]


class FromGrayscale(PublicModel):
    source_color_mode: Literal["grayscale"]
    target: Annotated[
        RGBTarget | GrayscaleNoOp | IndexedTarget, Field(discriminator="color_mode")
    ]


class FromIndexed(PublicModel):
    source_color_mode: Literal["indexed"]
    target: Annotated[
        RGBTarget | GrayscaleTarget | IndexedNoOp, Field(discriminator="color_mode")
    ]


Conversion = Annotated[
    FromRGB | FromGrayscale | FromIndexed, Field(discriminator="source_color_mode")
]


class ColorModeInput(PublicModel):
    conversion: Conversion


class ColorModeRequest(RuntimeRequest, ColorModeInput):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool

    _source = field_validator("source_sprite_file")(validate_native_sprite_path)
    _target = field_validator("target_sprite_file")(validate_native_sprite_path)

    @model_validator(mode="after")
    def validate_intent(self) -> "ColorModeRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class PaletteIndexCount(PublicModel):
    index: int = Field(ge=0)
    pixel_count: int = Field(ge=1)


class ConversionImage(PublicModel):
    image_number: int = Field(ge=1)
    kind: Literal["cel", "tilemap", "tile"]
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    bytes_per_pixel: int = Field(ge=1)
    row_stride: int = Field(ge=1)
    content: str = Field(pattern=r"^[0-9a-f]{16}$")
    conversion_frame_number: int | None = Field(ge=1)
    palette_frame_number: int | None = Field(ge=1)
    palette_indices: list[PaletteIndexCount] | None


class ConversionCel(PublicModel):
    layer_path: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    image_number: int = Field(ge=1)
    opacity: int = Field(ge=0, le=255)
    is_background: bool


class ConversionTile(PublicModel):
    tile_index: int = Field(ge=0)
    image_number: int | None = Field(ge=1)


class ConversionTileset(PublicModel):
    tileset_number: int = Field(ge=1)
    name: str
    tiles: list[ConversionTile]


class ColorModeDocument(PublicModel):
    color_mode: ColorMode
    transparent_color_index: int = Field(ge=0)
    palettes: PaletteTimeline
    images: list[ConversionImage]
    cels: list[ConversionCel]
    tilesets: list[ConversionTileset]


class MappingEvidence(PublicModel):
    requested_rgb_map_algorithm: RGBMapAlgorithm
    effective_rgb_map_algorithm: Literal["rgb5a3", "octree"]
    color_best_fit_criteria: ColorBestFitCriteria


class MatrixEvidence(PublicModel):
    provenance: Literal["native-default", "installed", "file"]
    requested: Matrix | None
    resolved_path: str | None
    identity: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class DitheringEvidence(PublicModel):
    requested_algorithm: Literal["none", "ordered", "old", "error-diffusion"]
    effective_algorithm: Literal["none", "ordered", "old", "error-diffusion"]
    matrix: MatrixEvidence | None
    dithering_factor: float | None = Field(ge=0, le=1, allow_inf_nan=False)


class ColorModeEvidence(PublicModel):
    source_color_mode: ColorMode
    target_color_mode: ColorMode
    changed: bool
    to_gray: ToGray | None
    mapping: MappingEvidence | None
    dithering: DitheringEvidence | None
    before: ColorModeDocument
    after: ColorModeDocument


class ColorModePersistedEvidence(ColorModeEvidence):
    persisted_reopen_verified: Literal[True]


class ColorModeResult(ColorModePersistedEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite change-color-mode"] = "spa sprite change-color-mode"
    target_commit: TargetCommit


COLOR_MODE_RESOURCE = PackagedResource("color_mode", "color/color_mode.lua")
COLOR_MODE_RESOURCES = (
    *SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    DIGEST_RESOURCE,
    EFFECTIVE_PALETTE_RESOURCE,
    PALETTE_SUPPORT_RESOURCE,
    COLOR_MODE_RESOURCE,
)
COLOR_MODE_HANDLER = PackagedHandler(
    "change_color_mode", "color/change_color_mode.lua", COLOR_MODE_RESOURCES
)
COLOR_MODE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_change_color_mode"],
)


def validate_evidence(request: ColorModeInput, evidence: ColorModeEvidence) -> None:
    conversion = request.conversion
    source, target = conversion.source_color_mode, conversion.target.color_mode
    if (
        evidence.source_color_mode != source
        or evidence.target_color_mode != target
        or evidence.before.color_mode != source
        or evidence.after.color_mode != target
        or evidence.changed != (source != target)
    ):
        raise ValueError("Color Mode evidence differs from the requested conversion")
    if source == target and evidence.before != evidence.after:
        raise ValueError("Same-mode conversion changed content")


def change_color_mode(
    request: ColorModeRequest, services: OperationServices
) -> ColorModeResult:
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
            COLOR_MODE_HANDLER,
            {
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(mutation.staged_sprite_file),
                "conversion": request.conversion.model_dump(exclude_none=True),
            },
            request.timeout_seconds,
        )
        try:
            evidence = ColorModePersistedEvidence.model_validate(invocation.payload)
            validate_evidence(request, evidence)
        except ValueError as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Invalid persisted Color Mode evidence",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        return ColorModeResult(**evidence.model_dump(), target_commit=mutation.commit())


COLOR_MODE_OPERATIONS = (
    OperationDescriptor(
        "sprite change-color-mode",
        ColorModeRequest,
        ColorModeResult,
        change_color_mode,
        lambda result: result.target_commit.target_sprite_file,
        COLOR_MODE_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        plan_eligible=True,
    ),
)
