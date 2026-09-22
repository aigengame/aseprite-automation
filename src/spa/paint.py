"""Paint Domain Module contracts, descriptor, and application orchestration."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, ValidationError, model_validator

from spa.contracts import PublicModel, RuntimeRequest, RuntimeRequirements
from spa.mutation import TargetCommit
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.ports import (
    KernelInvocationResult,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PostconditionEvidence,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.raster import (
    AllSelection,
    MaskSelection,
    PixelPatch,
    PixelRun,
    Point,
    Rectangle,
    RgbaColor,
    SelectionApplication,
)

OneBasedIndex = Annotated[int, Field(ge=1)]
MAX_PATCH_PIXELS = 256


def _native_sprite_path(value: str) -> str:
    if Path(value).suffix.lower() != ".aseprite":
        raise ValueError("Sprite file must use the .aseprite extension")
    return value


class CelAddress(PublicModel):
    layer_path: list[OneBasedIndex] = Field(min_length=1)
    frame_number: int = Field(ge=1)


class PaintPixelPatch(PixelPatch):
    model_config = ConfigDict(
        json_schema_extra={"x-spa-max-addressed-pixels": MAX_PATCH_PIXELS}
    )

    runs: list[PixelRun] = Field(
        max_length=MAX_PATCH_PIXELS,
        description=(
            "Canonical runs with at most 256 runs and 256 addressed Image Pixels "
            "in total."
        ),
    )


class PaintApplyRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    target: CelAddress
    patch: PaintPixelPatch
    clipping: Literal["reject", "clip"] = "reject"
    selection: SelectionApplication | None = None

    @model_validator(mode="after")
    def validate_target_commit_intent(self) -> "PaintApplyRequest":
        source = _native_sprite_path(self.source_sprite_file)
        target = _native_sprite_path(self.target_sprite_file)
        same_file = (
            Path(source).expanduser().absolute() == Path(target).expanduser().absolute()
        )
        if self.in_place:
            if not same_file:
                raise ValueError(
                    "in_place requires identical Source and Target Sprite Files"
                )
            if not self.overwrite:
                raise ValueError("in_place requires overwrite permission")
        elif same_file:
            raise ValueError(
                "identical Source and Target Sprite Files require in_place"
            )
        if (
            len(self.patch.runs) > MAX_PATCH_PIXELS
            or sum(run.length for run in self.patch.runs) > MAX_PATCH_PIXELS
        ):
            raise ValueError(
                f"Pixel Patch exceeds the {MAX_PATCH_PIXELS}-pixel Operation Limit"
            )
        return self


class AffectedCel(PublicModel):
    layer_path: list[OneBasedIndex] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    position: Point
    bounds: Rectangle
    linked_to_target: Literal[True]


class PaletteIndexFact(PublicModel):
    index: int = Field(ge=0, le=255)
    color: RgbaColor


class EffectivePaletteFact(PublicModel):
    frame_number: int = Field(ge=1)
    palette_frame_number: int = Field(ge=1)
    palette_size: int = Field(ge=1, le=256)
    indexes: list[PaletteIndexFact]


class ImageContentDigest(PublicModel):
    algorithm: Literal["sha256"] = "sha256"
    value: str = Field(pattern=r"^[0-9a-f]{64}$")


class PaintApplyEvidence(PublicModel):
    input_form: Literal["inline"]
    persisted_reopen_verified: Literal[True]
    target: CelAddress
    color_mode: Literal["rgb", "grayscale", "indexed"]
    clipping: Literal["reject", "clip"]
    selection: SelectionApplication | None = None
    requested_rectangle: Rectangle
    applied_rectangle: Rectangle
    requested_runs: list[PixelRun]
    applied_runs: list[PixelRun]
    skipped_by_bounds_runs: list[PixelRun]
    skipped_by_selection_runs: list[PixelRun]
    pixels_requested: int = Field(ge=0)
    pixels_written: int = Field(ge=0)
    pixels_changed: int = Field(ge=0)
    pixels_skipped_by_bounds: int = Field(ge=0)
    pixels_skipped_by_selection: int = Field(ge=0)
    affected_cels: list[AffectedCel] = Field(min_length=1)
    linked_cels_preserved: Literal[True]
    geometry_unchanged: Literal[True]
    background_opaque: bool
    effective_palettes: list[EffectivePaletteFact]
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest


class PaintApplyResult(PaintApplyEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa paint apply"] = "spa paint apply"
    target_commit: TargetCommit


PAINT_APPLY_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_paint_apply"],
)
PAINT_APPLY_FAILURE_CODES = (*RUNTIME_FAILURE_CODES, "target_commit_failed")
PAINT_SUPPORT_RESOURCE = PackagedResource("paint", "paint_apply_support.lua")
SHA256_RESOURCE = PackagedResource("sha256", "sha256.lua")
PAINT_PROBE_FIXTURE = PackagedResource("paint_fixture", "paint_apply_fixture.aseprite")
PAINT_PROBE_RESOURCES = (
    PAINT_SUPPORT_RESOURCE,
    SHA256_RESOURCE,
    PAINT_PROBE_FIXTURE,
)
PAINT_APPLY_HANDLER = PackagedHandler(
    "paint_apply", (PAINT_SUPPORT_RESOURCE, SHA256_RESOURCE)
)


def apply_paint(
    request: PaintApplyRequest, services: OperationServices
) -> PaintApplyResult:
    observation = services.probe_runtime(request)
    target_file = Path(request.target_sprite_file)
    staged_file = services.target_files.staged_path(target_file)
    payload = request.model_dump(
        mode="json",
        exclude={
            "aseprite",
            "timeout_seconds",
            "target_sprite_file",
            "in_place",
            "overwrite",
        },
    )
    payload["staged_sprite_file"] = str(staged_file)
    try:
        invocation = services.invoke_kernel(
            observation, PAINT_APPLY_HANDLER, payload, request.timeout_seconds
        )
        evidence = _paint_evidence(invocation)
        _validate_evidence(request, evidence, invocation)
        committed = services.target_files.commit(
            staged_file, target_file, overwrite=request.overwrite
        )
        return PaintApplyResult(
            **evidence.model_dump(),
            target_commit=TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
        )
    finally:
        services.target_files.discard(staged_file)


def _paint_evidence(invocation: KernelInvocationResult) -> PaintApplyEvidence:
    try:
        return PaintApplyEvidence.model_validate(invocation.payload)
    except (TypeError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Paint handler returned invalid mutation evidence",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc


def _validate_evidence(
    request: PaintApplyRequest,
    evidence: PaintApplyEvidence,
    invocation: KernelInvocationResult,
) -> None:
    requested_pixels = sum(run.length for run in request.patch.runs)
    applied_pixels = sum(run.length for run in evidence.applied_runs)
    bounds_pixels = sum(run.length for run in evidence.skipped_by_bounds_runs)
    selection_pixels = sum(run.length for run in evidence.skipped_by_selection_runs)
    target_cels = [
        cel
        for cel in evidence.affected_cels
        if (
            cel.layer_path == request.target.layer_path
            and cel.frame_number == request.target.frame_number
        )
    ]
    target_cel = target_cels[0] if len(target_cels) == 1 else None
    valid = (
        evidence.target == request.target
        and evidence.clipping == request.clipping
        and evidence.selection == request.selection
        and evidence.requested_rectangle.model_dump()
        == request.patch.rectangle.model_dump()
        and evidence.requested_runs == request.patch.runs
        and evidence.pixels_requested == requested_pixels
        and evidence.pixels_written == applied_pixels
        and evidence.pixels_skipped_by_bounds == bounds_pixels
        and evidence.pixels_skipped_by_selection == selection_pixels
        and requested_pixels == applied_pixels + bounds_pixels + selection_pixels
        and evidence.pixels_changed <= evidence.pixels_written
        and target_cel is not None
    )
    if valid and target_cel is not None:
        valid = _validate_pixel_partition(request, evidence, target_cel)
    if not valid:
        raise RuntimeIssue(
            "postcondition_failed",
            "Persisted Paint evidence differs from the declared request",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="requested, applied, skipped, or affected-Cel facts disagree",
            ),
            invocation.diagnostics,
        )


def _validate_pixel_partition(
    request: PaintApplyRequest,
    evidence: PaintApplyEvidence,
    target_cel: AffectedCel,
) -> bool:
    try:
        requested = _pixel_map(request.patch.runs)
        reported_requested = _pixel_map(evidence.requested_runs)
        applied = _pixel_map(evidence.applied_runs)
        skipped_bounds = _pixel_map(evidence.skipped_by_bounds_runs)
        skipped_selection = _pixel_map(evidence.skipped_by_selection_runs)
    except ValueError:
        return False

    category_coordinates = (
        set(applied),
        set(skipped_bounds),
        set(skipped_selection),
    )
    disjoint = all(
        left.isdisjoint(right)
        for index, left in enumerate(category_coordinates)
        for right in category_coordinates[index + 1 :]
    )
    reported_partition = applied | skipped_bounds | skipped_selection
    image_width = target_cel.bounds.width
    image_height = target_cel.bounds.height

    def in_bounds(coordinate: tuple[int, int]) -> bool:
        x, y = coordinate
        return 0 <= x < image_width and 0 <= y < image_height

    def selected(coordinate: tuple[int, int]) -> bool:
        x, y = coordinate
        return _selection_contains(
            request.selection,
            x + target_cel.position.x,
            y + target_cel.position.y,
        )

    rectangle = request.patch.rectangle
    rectangle_in_bounds = (
        rectangle.x >= 0
        and rectangle.y >= 0
        and rectangle.x + rectangle.width <= image_width
        and rectangle.y + rectangle.height <= image_height
    )
    expected_applied_rectangle = _bounding_rectangle(
        set(applied), rectangle.x, rectangle.y
    )
    digest_relation_valid = (
        evidence.before_content_digest == evidence.after_content_digest
        if evidence.pixels_changed == 0
        else evidence.before_content_digest != evidence.after_content_digest
    )
    return (
        target_cel.bounds.x == target_cel.position.x
        and target_cel.bounds.y == target_cel.position.y
        and image_width > 0
        and image_height > 0
        and requested == reported_requested
        and disjoint
        and requested == reported_partition
        and all(in_bounds(point) and selected(point) for point in applied)
        and all(not in_bounds(point) for point in skipped_bounds)
        and all(in_bounds(point) and not selected(point) for point in skipped_selection)
        and (request.clipping == "clip" or not skipped_bounds)
        and (request.clipping == "clip" or rectangle_in_bounds)
        and evidence.applied_rectangle.model_dump() == expected_applied_rectangle
        and digest_relation_valid
    )


def _pixel_map(runs: list[PixelRun]) -> dict[tuple[int, int], object]:
    result: dict[tuple[int, int], object] = {}
    for run in runs:
        color = run.color.model_dump(mode="json")
        for x in range(run.x, run.x + run.length):
            coordinate = (x, run.y)
            if coordinate in result:
                raise ValueError("duplicate Pixel coordinate")
            result[coordinate] = color
    return result


def _selection_contains(selection: SelectionApplication | None, x: int, y: int) -> bool:
    if selection is None:
        return True
    if selection.kind == "empty":
        return False
    bounds = (
        selection.rectangle if isinstance(selection, AllSelection) else selection.bounds
    )
    if not (
        bounds.x <= x < bounds.x + bounds.width
        and bounds.y <= y < bounds.y + bounds.height
    ):
        return False
    if isinstance(selection, AllSelection):
        return True
    assert isinstance(selection, MaskSelection)
    return any(
        row.y == y and any(run.x <= x < run.x + run.length for run in row.runs)
        for row in selection.rows
    )


def _bounding_rectangle(
    coordinates: set[tuple[int, int]], empty_x: int, empty_y: int
) -> dict[str, int]:
    if not coordinates:
        return {"x": empty_x, "y": empty_y, "width": 0, "height": 0}
    xs = [coordinate[0] for coordinate in coordinates]
    ys = [coordinate[1] for coordinate in coordinates]
    left, top = min(xs), min(ys)
    return {
        "x": left,
        "y": top,
        "width": max(xs) - left + 1,
        "height": max(ys) - top + 1,
    }


PAINT_OPERATIONS = (
    OperationDescriptor(
        "paint apply",
        PaintApplyRequest,
        PaintApplyResult,
        apply_paint,
        lambda result: result.target_commit.target_sprite_file,
        PAINT_APPLY_REQUIREMENTS,
        PAINT_APPLY_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
