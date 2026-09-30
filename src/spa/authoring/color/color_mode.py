"""Explicit native Color Mode paths and complete conversion evidence."""

from math import floor
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
    KernelInvocationResult,
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
    matrix: Matrix | None = Field(default_factory=lambda: None)

    @field_validator("matrix", mode="before", json_schema_input_type=Matrix)
    @classmethod
    def reject_null_matrix(cls, value: object) -> object:
        if value is None:
            raise ValueError(
                "Matrix cannot be null; omit it to select the native default"
            )
        return value


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

    @model_validator(mode="after")
    def validate_document(self) -> "ColorModeDocument":
        if [image.image_number for image in self.images] != list(
            range(1, len(self.images) + 1)
        ):
            raise ValueError(
                "Conversion Images must be complete and consecutively addressed"
            )
        referenced = {cel.image_number for cel in self.cels}
        referenced.update(
            tile.image_number
            for tileset in self.tilesets
            for tile in tileset.tiles
            if tile.image_number is not None
        )
        if referenced != set(range(1, len(self.images) + 1)):
            raise ValueError("Image references do not cover the observed Images")
        if len({(tuple(cel.layer_path), cel.frame_number) for cel in self.cels}) != len(
            self.cels
        ):
            raise ValueError("Duplicate Cel address")
        for image in self.images:
            expected_bpp = (
                4
                if image.kind == "tilemap"
                else {"rgb": 4, "grayscale": 2, "indexed": 1}[self.color_mode]
            )
            if (
                image.bytes_per_pixel != expected_bpp
                or image.row_stride < image.width * expected_bpp
            ):
                raise ValueError("Image layout differs from Color Mode")
            if image.kind == "tilemap":
                if (
                    image.conversion_frame_number is not None
                    or image.palette_frame_number is not None
                ):
                    raise ValueError(
                        "Tilemap cell indexes are not converted Image pixels"
                    )
            else:
                frame = image.conversion_frame_number
                if frame is None or not 1 <= frame <= self.palettes.frame_count:
                    raise ValueError("Invalid conversion Frame")
                supplying = next(
                    change
                    for change in reversed(self.palettes.palette_changes)
                    if change.palette_frame_number <= frame
                )
                if image.palette_frame_number != supplying.palette_frame_number:
                    raise ValueError(
                        "Image has an inconsistent Effective Palette basis"
                    )
            indexed = self.color_mode == "indexed" and image.kind != "tilemap"
            if indexed != (image.palette_indices is not None):
                raise ValueError("Palette Index observations differ from Color Mode")
            if image.palette_indices is not None:
                indexes = [item.index for item in image.palette_indices]
                if (
                    indexes != sorted(set(indexes))
                    or sum(item.pixel_count for item in image.palette_indices)
                    != image.width * image.height
                ):
                    raise ValueError(
                        "Palette Index observations do not cover the Image"
                    )
        if [tileset.tileset_number for tileset in self.tilesets] != list(
            range(1, len(self.tilesets) + 1)
        ):
            raise ValueError("Tileset observations must be complete and ordered")
        for tileset in self.tilesets:
            if [tile.tile_index for tile in tileset.tiles] != list(
                range(len(tileset.tiles))
            ):
                raise ValueError(
                    "Tile observations must include index zero and every Tile"
                )
        return self


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
    effective_factor_percent: int | None = Field(ge=0, le=100)


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


class ColorModeMismatchDetails(PublicModel):
    kind: Literal["color_mode"] = "color_mode"
    expected: ColorMode
    actual: ColorMode
    step_number: int | None = Field(default=None, ge=1)


class MatrixFailureDetails(PublicModel):
    kind: Literal["dithering_matrix"] = "dithering_matrix"
    matrix: Matrix
    reason: Literal["missing", "ambiguous", "unreadable", "invalid"]
    matches: list[str]
    step_number: int | None = Field(default=None, ge=1)


COLOR_MODE_FAILURE_SPECS = (
    FailureCodeSpec(
        "color_mode_mismatch",
        "Actual Source Color Mode differs from the selected branch",
        "input",
        ColorModeMismatchDetails,
    ),
    FailureCodeSpec(
        "dithering_matrix_invalid",
        "Requested Dithering Matrix could not be resolved and loaded uniquely",
        "input",
        MatrixFailureDetails,
    ),
)


def reject_color_mode(
    invocation: KernelInvocationResult, rejected: object, step_number: int | None = None
) -> None:
    if rejected is None:
        return
    try:
        if not isinstance(rejected, dict):
            raise TypeError("Invalid Color Mode rejection")
        spec = next(
            item for item in COLOR_MODE_FAILURE_SPECS if item.code == rejected["code"]
        )
        assert spec.details_type is not None
        details = spec.details_type.model_validate(
            {**rejected["details"], "step_number": step_number}
        )
        message = rejected["message"]
        if not isinstance(message, str):
            raise TypeError("Rejection message must be text")
    except (KeyError, TypeError, ValueError, StopIteration) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Invalid Color Mode rejection",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc
    raise OperationIssue(spec.code, message, details)


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
    before, after = evidence.before, evidence.after
    if (
        evidence.source_color_mode != source
        or evidence.target_color_mode != target
        or before.color_mode != source
        or after.color_mode != target
        or evidence.changed != (source != target)
    ):
        raise ValueError("Color Mode evidence differs from the requested conversion")
    if source == target and before != after:
        raise ValueError("Same-mode conversion changed content")
    options = conversion.target
    if evidence.to_gray != (
        options.to_gray if isinstance(options, GrayscaleTarget) else None
    ):
        raise ValueError("To Gray evidence differs from the requested conversion")
    if isinstance(options, IndexedTarget):
        mapping = evidence.mapping
        if (
            mapping is None
            or mapping.requested_rgb_map_algorithm != options.rgb_map_algorithm
            or mapping.color_best_fit_criteria != options.color_best_fit_criteria
            or (
                options.rgb_map_algorithm != "default"
                and mapping.effective_rgb_map_algorithm != options.rgb_map_algorithm
            )
        ):
            raise ValueError("Native mapping evidence differs from explicit choices")
    elif evidence.mapping is not None:
        raise ValueError("Inapplicable native mapping evidence")
    if isinstance(options, DitheredIndexedTarget):
        requested, observed = options.dithering, evidence.dithering
        if (
            observed is None
            or observed.requested_algorithm != requested.algorithm
            or observed.effective_algorithm != requested.algorithm
        ):
            raise ValueError("Dithering algorithm differs from the request")
        factor = (
            requested.dithering_factor
            if isinstance(requested, ErrorDiffusion)
            else None
        )
        if observed.dithering_factor != factor or observed.effective_factor_percent != (
            floor(factor * 100) if factor is not None else None
        ):
            raise ValueError("Dithering Factor differs from the native request")
        if isinstance(requested, MatrixDithering):
            matrix = observed.matrix
            if matrix is None or matrix.requested != requested.matrix:
                raise ValueError("Matrix resolution differs from the request")
            if requested.matrix is None:
                if matrix != MatrixEvidence(
                    provenance="native-default",
                    requested=None,
                    resolved_path=None,
                    identity="bayer8x8",
                    width=8,
                    height=8,
                ):
                    raise ValueError("Native default Matrix evidence is invalid")
            elif matrix.provenance != requested.matrix.kind or not matrix.resolved_path:
                raise ValueError("Explicit Matrix was not resolved")
            elif (
                isinstance(requested.matrix, InstalledMatrix)
                and matrix.identity != requested.matrix.id
            ):
                raise ValueError(
                    "Installed Matrix identity differs from the requested ID"
                )
        elif observed.matrix is not None:
            raise ValueError("Inapplicable Dithering Matrix")
    elif evidence.dithering is not None:
        raise ValueError("Inapplicable Dithering evidence")
    if (
        before.palettes.frame_count != after.palettes.frame_count
        or before.tilesets != after.tilesets
    ):
        raise ValueError("Conversion changed the Sprite structure")
    if source != target and target != "grayscale" and before.palettes != after.palettes:
        raise ValueError("Conversion did not preserve the existing Palette basis")
    if len(before.images) != len(after.images) or len(before.cels) != len(after.cels):
        raise ValueError("Conversion lost Image or Cel observations")
    for old, new in zip(before.images, after.images, strict=True):
        if (old.kind, old.width, old.height, old.conversion_frame_number) != (
            new.kind,
            new.width,
            new.height,
            new.conversion_frame_number,
        ):
            raise ValueError("Conversion changed Image identity or dimensions")
        if old.kind == "tilemap" and old != new:
            raise ValueError("Conversion rewrote Tilemap cell indexes")
    for old, new in zip(before.cels, after.cels, strict=True):
        expected = (
            old.model_copy(update={"opacity": 255})
            if source != target and target == "indexed"
            else old
        )
        if new != expected:
            raise ValueError(
                "Conversion changed Cel addresses, links, or unexpected Layer/opacity facts"
            )


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
        reject_color_mode(invocation, invocation.payload.get("rejection"))
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
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            *(item.code for item in COLOR_MODE_FAILURE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        plan_eligible=True,
    ),
)
