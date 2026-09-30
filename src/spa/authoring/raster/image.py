"""Cel-targeted Image transforms with explicit placement and verified publication."""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal, Self, cast

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.document.cel import CelAddress, CelState, CelTargetDetails, _reject
from spa.authoring.document.layer import LAYER_ADDRESS_FAILURE_CODES
from spa.authoring.document.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteGetRequest,
    SpriteInspection,
    validated_scope,
)
from spa.authoring.raster.image_snapshot import IMAGE_SNAPSHOT_OPERATIONS
from spa.contracts.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    source_target_identity_issue,
    validate_native_sprite_path,
)
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PostconditionEvidence,
    RequestIssue,
    ResponseEvidence,
    RuntimeIssue,
    TargetCommitEvidence,
)
from spa.contracts.public import (
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.contracts.raster import (
    ColorValue,
    ImageContentDigest,
    Point,
    PositiveRectangle,
    Rectangle,
    Size,
)
from spa.contracts.rounding import ROUNDING_RESOURCE, Rounding

ResizeMethod = Literal["nearest-neighbor", "bilinear", "rotsprite"]


class KeepPosition(PublicModel):
    kind: Literal["keep"] = "keep"


class PivotPosition(PublicModel):
    kind: Literal["pivot"] = "pivot"
    pivot_x: int = Field(ge=-(2**31), le=2**31 - 1, strict=True)
    pivot_y: int = Field(ge=-(2**31), le=2**31 - 1, strict=True)
    rounding: Rounding


PositionPolicy = Annotated[KeepPosition | PivotPosition, Field(discriminator="kind")]


class _ImageMutationRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    target: CelAddress

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_publication_intent(self) -> Self:
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class ImageResizeRequest(_ImageMutationRequest):
    width: int = Field(ge=1, le=65535, strict=True)
    height: int = Field(ge=1, le=65535, strict=True)
    method: ResizeMethod
    position_policy: PositionPolicy
    palette_frame_number: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def validate_intent(self) -> "ImageResizeRequest":
        if self.method != "bilinear" and self.palette_frame_number is not None:
            raise ValueError("palette_frame_number is only valid for bilinear")
        return self


class ImageFlipRequest(_ImageMutationRequest):
    axis: Literal["horizontal", "vertical"]


class RotationPivotPosition(PublicModel):
    kind: Literal["pivot"] = "pivot"
    pivot_x: int = Field(
        ge=-(2**31),
        le=2**31 - 1,
        strict=True,
        description="Integer x in old Image Pixel space; may be outside the Image",
    )
    pivot_y: int = Field(
        ge=-(2**31),
        le=2**31 - 1,
        strict=True,
        description="Integer y in old Image Pixel space; may be outside the Image",
    )


RotationPositionPolicy = Annotated[
    KeepPosition | RotationPivotPosition, Field(discriminator="kind")
]


class ImageRotateRequest(_ImageMutationRequest):
    angle: Literal[90, -90, 180]
    position_policy: RotationPositionPolicy

    @field_validator("angle", mode="before")
    @classmethod
    def require_integer_angle(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("angle must be an integer quarter turn")
        return value


class ImageCelEffect(PublicModel):
    before: CelState
    after: CelState
    before_bounds: Rectangle
    after_bounds: Rectangle


class ImageOrientationInvariants(PublicModel):
    sprite_structure: Literal[True]
    unrelated_cels: Literal[True]
    cel_opacity_and_z_index: Literal[True]
    color_mode: Literal[True]


class ImageOrientationEvidence(PublicModel):
    target: CelAddress
    image_coordinate_space: Literal["image-pixel"]
    cel_coordinate_space: Literal["canvas-pixel"]
    old_size: Size
    new_size: Size
    position_delta: Point
    color_mode: Literal["rgb", "grayscale", "indexed"]
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest
    affected_cels: list[ImageCelEffect] = Field(min_length=1)
    native_sharing_preserved: Literal[True]
    unchanged_native_invariants: ImageOrientationInvariants
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]


class ImageFlipEvidence(ImageOrientationEvidence):
    axis: Literal["horizontal", "vertical"]


class ImageFlipResult(ImageFlipEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image flip"] = "spa image flip"
    target_commit: TargetCommit


class ImageRotateEvidence(ImageOrientationEvidence):
    angle: Literal[90, -90, 180]
    position_policy: RotationPositionPolicy


class ImageRotateResult(ImageRotateEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image rotate"] = "spa image rotate"
    target_commit: TargetCommit


class RationalOffset(PublicModel):
    numerator: int
    denominator: int = Field(ge=1)
    applied: int


class EffectivePaletteBasis(PublicModel):
    requested_frame_number: int = Field(ge=1)
    palette_frame_number: int = Field(ge=1)
    palette_size: int = Field(ge=1)
    transparent_color_index: int = Field(ge=0, le=255)


class AffectedImageCel(PublicModel):
    layer_path: list[int] = Field(min_length=1)
    frame_number: int = Field(ge=1)
    before_position: Point = Field(
        description="Cel origin in Canvas Pixel space before the Mutation"
    )
    after_position: Point = Field(
        description="Cel origin in Canvas Pixel space after the Mutation"
    )
    before_image_bounds: Size
    after_image_bounds: Size


class _ImageMutationEvidence(PublicModel):
    target: CelAddress
    color_mode: Literal["rgb", "grayscale", "indexed"]
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest
    affected_cels: list[AffectedImageCel] = Field(min_length=1)
    native_sharing_preserved: Literal[True]
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]


class ImageResizeEvidence(_ImageMutationEvidence):
    old_size: Size
    requested_size: Size
    effective_size: Size
    method: ResizeMethod
    position_policy: PositionPolicy
    offset_x: RationalOffset
    offset_y: RationalOffset
    effective_palette: EffectivePaletteBasis | None


class ImageResizeResult(ImageResizeEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image resize"] = "spa image resize"
    target_commit: TargetCommit


class ImageRotatePositionDetails(PublicModel):
    kind: Literal["image_rotate_position"] = "image_rotate_position"
    target: CelAddress
    coordinate_space: Literal["canvas-pixel"]
    attempted_position: Point
    allowed_minimum: int = Field(
        strict=True, description="Inclusive minimum for each Canvas Pixel coordinate"
    )
    allowed_maximum: int = Field(
        strict=True, description="Inclusive maximum for each Canvas Pixel coordinate"
    )


IMAGE_RESIZE_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "image_resize_palette_basis_invalid",
        "The declared Frame cannot supply the required Effective Palette",
        "input",
        CelTargetDetails,
    ),
    FailureCodeSpec(
        "image_resize_position_out_of_bounds",
        "A resulting Cel position is outside the native signed 16-bit range",
        "input",
        CelTargetDetails,
    ),
)

IMAGE_ROTATE_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "image_rotate_position_out_of_bounds",
        "A resulting Cel position is outside the native signed 16-bit range",
        "input",
        ImageRotatePositionDetails,
    ),
)

IMAGE_RESIZE_TRANSFORM_RESOURCE = PackagedResource(
    "image_resize_transform", "image_resize_transform.lua"
)
IMAGE_CEL_MUTATION_RESOURCE = PackagedResource(
    "image_cel_mutation", "image_cel_mutation.lua"
)
IMAGE_MUTATION_RESOURCES = (
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_PERSISTENCE_RESOURCE,
    PackagedResource("layer_select", "layer_select.lua"),
    PackagedResource("cel", "cel_support.lua"),
    PackagedResource("digest", "digest.lua"),
    IMAGE_CEL_MUTATION_RESOURCE,
)
IMAGE_RESIZE_HANDLER = PackagedHandler(
    "image_resize",
    (
        *IMAGE_MUTATION_RESOURCES,
        IMAGE_RESIZE_TRANSFORM_RESOURCE,
        EFFECTIVE_PALETTE_RESOURCE,
        ROUNDING_RESOURCE,
    ),
)

IMAGE_RESIZE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_image_resize",
        "aseprite_cel_lifecycle",
        "aseprite_cel_relationships",
        "aseprite_sprite_inspection",
    ],
)

IMAGE_ORIENTATION_TRANSFORM_RESOURCE = PackagedResource(
    "image_orientation_transform", "image_orientation_transform.lua"
)
IMAGE_ORIENTATION_HANDLER = PackagedHandler(
    "image_orientation",
    (
        SPRITE_INSPECTION_RESOURCE,
        SPRITE_PERSISTENCE_RESOURCE,
        PackagedResource("layer_select", "layer_select.lua"),
        PackagedResource("cel", "cel_support.lua"),
        PackagedResource("digest", "digest.lua"),
        IMAGE_ORIENTATION_TRANSFORM_RESOURCE,
    ),
)
IMAGE_FLIP_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_image_flip",
        "aseprite_cel_lifecycle",
        "aseprite_cel_relationships",
        "aseprite_sprite_inspection",
    ],
)
IMAGE_ROTATE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_image_rotate",
        "aseprite_cel_lifecycle",
        "aseprite_cel_relationships",
        "aseprite_sprite_inspection",
    ],
)


def _orient_image(
    request: ImageFlipRequest | ImageRotateRequest, services: OperationServices
) -> ImageFlipResult | ImageRotateResult:
    operation = "flip" if isinstance(request, ImageFlipRequest) else "rotate"
    source = Path(request.source_sprite_file)
    target_file = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files, source, target_file, request.in_place
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    observation = services.probe_runtime(request)
    staged = services.target_files.staged_path(target_file)
    try:
        payload: dict[str, object] = {
            "operation": operation,
            "source_sprite_file": request.source_sprite_file,
            "staged_sprite_file": str(staged),
            "target": request.target.model_dump(mode="json", exclude_none=True),
        }
        if isinstance(request, ImageFlipRequest):
            payload["axis"] = request.axis
        else:
            payload.update(
                angle=request.angle,
                position_policy=request.position_policy.model_dump(mode="json"),
            )
        invocation = services.invoke_kernel(
            observation, IMAGE_ORIENTATION_HANDLER, payload, request.timeout_seconds
        )
        rejection = invocation.payload.get("rejection")
        if (
            isinstance(request, ImageRotateRequest)
            and isinstance(rejection, dict)
            and rejection.get("code") == "image_rotate_position_out_of_bounds"
            and isinstance(rejection.get("message"), str)
        ):
            try:
                facts = rejection.get("details")
                if not isinstance(facts, dict):
                    raise TypeError("missing rotation position failure facts")
                details = ImageRotatePositionDetails.model_validate(
                    {**facts, "target": request.target}
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raise RuntimeIssue(
                    "response_malformed",
                    f"Packaged Image Rotate handler returned invalid failure facts: {exc}",
                    ResponseEvidence(response_path=invocation.response_path),
                    invocation.diagnostics,
                ) from exc
            raise OperationIssue(
                rejection["code"],
                rejection["message"],
                details,
            )
        number = request.target.frame_number
        _reject(invocation, request.target.layer, request.target, (number, number))
        try:
            evidence = (
                ImageFlipEvidence.model_validate(invocation.payload)
                if isinstance(request, ImageFlipRequest)
                else ImageRotateEvidence.model_validate(invocation.payload)
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Packaged Image {operation} handler returned invalid evidence: {exc}",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        validated_scope(
            SpriteGetRequest(
                sprite_file=request.target_sprite_file,
                inspection_scope=list(INSPECTION_SECTIONS),
            ),
            evidence.sprite,
            invocation,
        )
        matches_transform = (
            isinstance(evidence, ImageFlipEvidence)
            and isinstance(request, ImageFlipRequest)
            and evidence.axis == request.axis
            and evidence.new_size == evidence.old_size
            and evidence.position_delta == Point(x=0, y=0)
        ) or (
            isinstance(evidence, ImageRotateEvidence)
            and isinstance(request, ImageRotateRequest)
            and evidence.angle == request.angle
            and evidence.position_policy == request.position_policy
        )
        if (
            not matches_transform
            or evidence.target.frame_number != number
            or evidence.color_mode != evidence.sprite.metadata.color_mode
            or (
                request.target.layer.layer_path is not None
                and evidence.target.layer.layer_path != request.target.layer.layer_path
            )
        ):
            raise RuntimeIssue(
                "postcondition_failed",
                f"Persisted Image {operation} evidence differs from the request",
                PostconditionEvidence(
                    response_path=invocation.response_path,
                    reason="Image axis, dimensions, placement, or target disagrees",
                ),
                invocation.diagnostics,
            )
        if (
            source_target_identity_issue(
                services.target_files, source, target_file, request.in_place
            )
            is not None
        ):
            raise RuntimeIssue(
                "target_commit_failed",
                "Source/Target publication identity changed before Target Commit",
                TargetCommitEvidence(
                    str(target_file), "source_target_identity_changed"
                ),
            )
        committed = services.target_files.commit(
            staged, target_file, overwrite=request.overwrite
        )
        fields = {
            **evidence.model_dump(),
            "target_commit": TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
        }
        return (
            ImageFlipResult.model_validate(fields)
            if isinstance(request, ImageFlipRequest)
            else ImageRotateResult.model_validate(fields)
        )
    finally:
        services.target_files.discard(staged)


def flip_image(
    request: ImageFlipRequest, services: OperationServices
) -> ImageFlipResult:
    return cast(ImageFlipResult, _orient_image(request, services))


def rotate_image(
    request: ImageRotateRequest, services: OperationServices
) -> ImageRotateResult:
    return cast(ImageRotateResult, _orient_image(request, services))


class ImageCropRectangle(PositiveRectangle):
    x: int = Field(ge=-(2**31), le=2**31 - 1)
    y: int = Field(ge=-(2**31), le=2**31 - 1)
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)


class ImageCropRequest(_ImageMutationRequest):
    coordinate_space: Literal["image-pixel"]
    rectangle: ImageCropRectangle
    position_policy: Literal["preserve_canvas_pixels", "keep_cel_position"]


class ImageCanvasOffset(Point):
    x: int = Field(ge=-(2**31), le=2**31 - 1)
    y: int = Field(ge=-(2**31), le=2**31 - 1)


class ImageCanvasResizeRequest(_ImageMutationRequest):
    coordinate_space: Literal["image-pixel"]
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)
    offset: ImageCanvasOffset
    fill: ColorValue
    position_policy: Literal["keep_cel_position", "preserve_source_canvas"]


class ImageCanvasEvidence(_ImageMutationEvidence):
    coordinate_space: Literal["image-pixel"]
    source_bounds: PositiveRectangle = Field(
        description="Bounds in source Image Pixel space"
    )
    target_bounds: PositiveRectangle = Field(
        description="Bounds in target Image Pixel space"
    )
    copied_source_rectangle: Rectangle
    copied_target_rectangle: Rectangle
    discarded_source_regions: list[PositiveRectangle]
    uncovered_target_regions: list[PositiveRectangle]
    position_delta: Point = Field(
        description="Translation applied to every affected Cel in Canvas Pixel space"
    )


class ImageCropEvidence(ImageCanvasEvidence):
    rectangle: ImageCropRectangle
    position_policy: Literal["preserve_canvas_pixels", "keep_cel_position"]


class ImageCropResult(ImageCropEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image crop"] = "spa image crop"
    target_commit: TargetCommit


class ImageCanvasResizeEvidence(ImageCanvasEvidence):
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)
    offset: ImageCanvasOffset
    fill: ColorValue
    position_policy: Literal["keep_cel_position", "preserve_source_canvas"]


class ImageCanvasResizeResult(ImageCanvasResizeEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image canvas-resize"] = "spa image canvas-resize"
    target_commit: TargetCommit


IMAGE_CANVAS_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "image_canvas_fill_invalid",
        "Fill Color Value is incompatible with the Image or its Effective Palettes",
        "input",
        CelTargetDetails,
    ),
    FailureCodeSpec(
        "image_crop_out_of_bounds",
        "Crop Rectangle is outside the source Image",
        "input",
        CelTargetDetails,
    ),
    FailureCodeSpec(
        "image_transform_position_out_of_bounds",
        "A resulting Cel position is outside the native signed 16-bit range",
        "input",
        CelTargetDetails,
    ),
)
IMAGE_CANVAS_TRANSFORM_RESOURCE = PackagedResource(
    "image_canvas_transform", "image_canvas_transform.lua"
)
IMAGE_CANVAS_RESOURCES = (*IMAGE_MUTATION_RESOURCES, IMAGE_CANVAS_TRANSFORM_RESOURCE)
IMAGE_CROP_HANDLER = PackagedHandler("image_crop", IMAGE_CANVAS_RESOURCES)
IMAGE_CANVAS_RESIZE_HANDLER = PackagedHandler(
    "image_canvas_resize", (*IMAGE_CANVAS_RESOURCES, EFFECTIVE_PALETTE_RESOURCE)
)
IMAGE_CANVAS_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_image_canvas_transform",
        "aseprite_cel_lifecycle",
        "aseprite_cel_relationships",
        "aseprite_sprite_inspection",
    ],
)


def _mutate_image[Evidence: _ImageMutationEvidence, Result: _ImageMutationEvidence](
    request: _ImageMutationRequest,
    services: OperationServices,
    handler: PackagedHandler,
    evidence_type: type[Evidence],
    result_type: type[Result],
    failure_codes: tuple[str, ...],
    matches: Callable[[Evidence], bool],
) -> Result:
    source, target_file = (
        Path(request.source_sprite_file),
        Path(request.target_sprite_file),
    )
    issue = source_target_identity_issue(
        services.target_files, source, target_file, request.in_place
    )
    if issue is not None:
        raise RequestIssue([issue])
    observation = services.probe_runtime(request)
    staged = services.target_files.staged_path(target_file)
    try:
        payload = request.model_dump(
            mode="json",
            exclude_none=True,
            exclude={
                "aseprite",
                "timeout_seconds",
                "target_sprite_file",
                "in_place",
                "overwrite",
            },
        )
        payload["staged_sprite_file"] = str(staged)
        invocation = services.invoke_kernel(
            observation, handler, payload, request.timeout_seconds
        )
        rejection = invocation.payload.get("rejection")
        if (
            isinstance(rejection, dict)
            and isinstance(rejection.get("code"), str)
            and rejection["code"] in failure_codes
            and isinstance(rejection.get("message"), str)
        ):
            raise OperationIssue(
                rejection["code"],
                rejection["message"],
                CelTargetDetails(target=request.target),
            )
        number = request.target.frame_number
        _reject(invocation, request.target.layer, request.target, (number, number))
        try:
            evidence = evidence_type.model_validate(invocation.payload)
        except (TypeError, ValueError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Packaged Image handler returned invalid evidence: {exc}",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        validated_scope(
            SpriteGetRequest(
                sprite_file=request.target_sprite_file,
                inspection_scope=list(INSPECTION_SECTIONS),
            ),
            evidence.sprite,
            invocation,
        )
        if (
            not matches(evidence)
            or evidence.target.frame_number != number
            or (
                request.target.layer.layer_path is not None
                and evidence.target.layer.layer_path != request.target.layer.layer_path
            )
            or evidence.color_mode != evidence.sprite.metadata.color_mode
        ):
            raise RuntimeIssue(
                "postcondition_failed",
                "Persisted Image evidence differs from the request",
                PostconditionEvidence(
                    response_path=invocation.response_path,
                    reason="Image target or transform intent disagrees",
                ),
                invocation.diagnostics,
            )
        if (
            source_target_identity_issue(
                services.target_files, source, target_file, request.in_place
            )
            is not None
        ):
            raise RuntimeIssue(
                "target_commit_failed",
                "Source/Target publication identity changed before Target Commit",
                TargetCommitEvidence(
                    str(target_file), "source_target_identity_changed"
                ),
            )
        committed = services.target_files.commit(
            staged, target_file, overwrite=request.overwrite
        )
        return result_type.model_validate(
            {
                **evidence.model_dump(),
                "target_commit": TargetCommit(
                    target_sprite_file=committed.target_sprite_file,
                    byte_size=committed.byte_size,
                    sha256=committed.sha256,
                ),
            }
        )
    finally:
        services.target_files.discard(staged)


IMAGE_CROP_FAILURE_CODES = (
    "image_crop_out_of_bounds",
    "image_transform_position_out_of_bounds",
)
IMAGE_CANVAS_RESIZE_FAILURE_CODES = (
    "image_canvas_fill_invalid",
    "image_transform_position_out_of_bounds",
)


def resize_image(
    request: ImageResizeRequest, services: OperationServices
) -> ImageResizeResult:
    def matches(evidence: ImageResizeEvidence) -> bool:
        indexed_bilinear = (
            request.method == "bilinear" and evidence.color_mode == "indexed"
        )
        return (
            evidence.requested_size == Size(width=request.width, height=request.height)
            and evidence.effective_size == evidence.requested_size
            and evidence.method == request.method
            and evidence.position_policy == request.position_policy
            and (
                (
                    evidence.effective_palette is not None
                    and evidence.effective_palette.requested_frame_number
                    == request.palette_frame_number
                )
                if indexed_bilinear
                else evidence.effective_palette is None
            )
        )

    return _mutate_image(
        request,
        services,
        IMAGE_RESIZE_HANDLER,
        ImageResizeEvidence,
        ImageResizeResult,
        tuple(spec.code for spec in IMAGE_RESIZE_FAILURE_CODE_SPECS),
        matches,
    )


def crop_image(
    request: ImageCropRequest, services: OperationServices
) -> ImageCropResult:
    return _mutate_image(
        request,
        services,
        IMAGE_CROP_HANDLER,
        ImageCropEvidence,
        ImageCropResult,
        IMAGE_CROP_FAILURE_CODES,
        lambda evidence: (
            evidence.rectangle == request.rectangle
            and evidence.position_policy == request.position_policy
        ),
    )


def canvas_resize_image(
    request: ImageCanvasResizeRequest, services: OperationServices
) -> ImageCanvasResizeResult:
    return _mutate_image(
        request,
        services,
        IMAGE_CANVAS_RESIZE_HANDLER,
        ImageCanvasResizeEvidence,
        ImageCanvasResizeResult,
        IMAGE_CANVAS_RESIZE_FAILURE_CODES,
        lambda evidence: (
            (
                evidence.width,
                evidence.height,
                evidence.offset,
                evidence.fill,
                evidence.position_policy,
            )
            == (
                request.width,
                request.height,
                request.offset,
                request.fill,
                request.position_policy,
            )
        ),
    )


IMAGE_OPERATIONS = (
    OperationDescriptor(
        "image resize",
        ImageResizeRequest,
        ImageResizeResult,
        resize_image,
        lambda result: result.target_commit.target_sprite_file,
        IMAGE_RESIZE_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "cel_not_found",
            "cel_frame_out_of_bounds",
            "cel_unsupported_target",
            *LAYER_ADDRESS_FAILURE_CODES,
            *(spec.code for spec in IMAGE_RESIZE_FAILURE_CODE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    *IMAGE_SNAPSHOT_OPERATIONS,
    OperationDescriptor(
        "image crop",
        ImageCropRequest,
        ImageCropResult,
        crop_image,
        lambda result: result.target_commit.target_sprite_file,
        IMAGE_CANVAS_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "cel_not_found",
            "cel_frame_out_of_bounds",
            "cel_unsupported_target",
            *LAYER_ADDRESS_FAILURE_CODES,
            *IMAGE_CROP_FAILURE_CODES,
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "image canvas-resize",
        ImageCanvasResizeRequest,
        ImageCanvasResizeResult,
        canvas_resize_image,
        lambda result: result.target_commit.target_sprite_file,
        IMAGE_CANVAS_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "cel_not_found",
            "cel_frame_out_of_bounds",
            "cel_unsupported_target",
            *LAYER_ADDRESS_FAILURE_CODES,
            *IMAGE_CANVAS_RESIZE_FAILURE_CODES,
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "image flip",
        ImageFlipRequest,
        ImageFlipResult,
        flip_image,
        lambda result: result.target_commit.target_sprite_file,
        IMAGE_FLIP_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "cel_not_found",
            "cel_frame_out_of_bounds",
            "cel_unsupported_target",
            *LAYER_ADDRESS_FAILURE_CODES,
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "image rotate",
        ImageRotateRequest,
        ImageRotateResult,
        rotate_image,
        lambda result: result.target_commit.target_sprite_file,
        IMAGE_ROTATE_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "cel_not_found",
            "cel_frame_out_of_bounds",
            "cel_unsupported_target",
            *LAYER_ADDRESS_FAILURE_CODES,
            *(spec.code for spec in IMAGE_ROTATE_FAILURE_CODE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
