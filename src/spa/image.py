"""Cel-targeted Image Resize with independent placement policy."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.cel import CelAddress, CelTargetDetails, _reject
from spa.contracts import (
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.layer import LAYER_ADDRESS_FAILURE_CODES
from spa.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    source_target_identity_issue,
    validate_native_sprite_path,
)
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.ports import (
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
from spa.raster import ImageContentDigest, Point, Size
from spa.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteGetRequest,
    SpriteInspection,
    validated_scope,
)

ResizeMethod = Literal["nearest-neighbor", "bilinear", "rotsprite"]
Rounding = Literal["toward-zero", "floor", "ceil", "nearest-away-from-zero"]


class KeepPosition(PublicModel):
    kind: Literal["keep"] = "keep"


class PivotPosition(PublicModel):
    kind: Literal["pivot"] = "pivot"
    pivot_x: int = Field(ge=-(2**31), le=2**31 - 1, strict=True)
    pivot_y: int = Field(ge=-(2**31), le=2**31 - 1, strict=True)
    rounding: Rounding


PositionPolicy = Annotated[KeepPosition | PivotPosition, Field(discriminator="kind")]


class ImageResizeRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    target: CelAddress
    width: int = Field(ge=1, le=65535, strict=True)
    height: int = Field(ge=1, le=65535, strict=True)
    method: ResizeMethod
    position_policy: PositionPolicy
    palette_frame_number: int | None = Field(default=None, ge=1, strict=True)

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_intent(self) -> "ImageResizeRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        if self.method != "bilinear" and self.palette_frame_number is not None:
            raise ValueError("palette_frame_number is only valid for bilinear")
        return self


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
    before_position: Point
    after_position: Point
    before_image_bounds: Size
    after_image_bounds: Size


class ImageResizeEvidence(PublicModel):
    target: CelAddress
    old_size: Size
    requested_size: Size
    effective_size: Size
    method: ResizeMethod
    position_policy: PositionPolicy
    offset_x: RationalOffset
    offset_y: RationalOffset
    color_mode: Literal["rgb", "grayscale", "indexed"]
    effective_palette: EffectivePaletteBasis | None
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest
    affected_cels: list[AffectedImageCel] = Field(min_length=1)
    native_sharing_preserved: Literal[True]
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]


class ImageResizeResult(ImageResizeEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image resize"] = "spa image resize"
    target_commit: TargetCommit


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

IMAGE_RESIZE_TRANSFORM_RESOURCE = PackagedResource(
    "image_resize_transform", "image_resize_transform.lua"
)
IMAGE_RESIZE_HANDLER = PackagedHandler(
    "image_resize",
    (
        SPRITE_INSPECTION_RESOURCE,
        SPRITE_PERSISTENCE_RESOURCE,
        PackagedResource("layer_select", "layer_select.lua"),
        PackagedResource("cel", "cel_support.lua"),
        PackagedResource("digest", "digest.lua"),
        IMAGE_RESIZE_TRANSFORM_RESOURCE,
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


def _postcondition(invocation, reason: str) -> RuntimeIssue:
    return RuntimeIssue(
        "postcondition_failed",
        "Persisted Image Resize evidence differs from the request",
        PostconditionEvidence(response_path=invocation.response_path, reason=reason),
        invocation.diagnostics,
    )


def resize_image(
    request: ImageResizeRequest, services: OperationServices
) -> ImageResizeResult:
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
            "source_sprite_file": request.source_sprite_file,
            "staged_sprite_file": str(staged),
            "target": request.target.model_dump(mode="json", exclude_none=True),
            "width": request.width,
            "height": request.height,
            "method": request.method,
            "position_policy": request.position_policy.model_dump(mode="json"),
        }
        if request.palette_frame_number is not None:
            payload["palette_frame_number"] = request.palette_frame_number
        invocation = services.invoke_kernel(
            observation,
            IMAGE_RESIZE_HANDLER,
            payload,
            request.timeout_seconds,
        )
        rejection = invocation.payload.get("rejection")
        if (
            isinstance(rejection, dict)
            and isinstance(rejection.get("code"), str)
            and rejection["code"]
            in {spec.code for spec in IMAGE_RESIZE_FAILURE_CODE_SPECS}
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
            evidence = ImageResizeEvidence.model_validate(invocation.payload)
        except (TypeError, ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Packaged Image Resize handler returned invalid evidence: {exc}",
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
            evidence.requested_size != Size(width=request.width, height=request.height)
            or evidence.effective_size != evidence.requested_size
            or evidence.method != request.method
            or evidence.position_policy != request.position_policy
            or evidence.target.frame_number != number
            or (
                request.target.layer.layer_path is not None
                and evidence.target.layer.layer_path != request.target.layer.layer_path
            )
            or evidence.color_mode != evidence.sprite.metadata.color_mode
            or (
                request.method == "bilinear"
                and evidence.color_mode == "indexed"
                and (
                    evidence.effective_palette is None
                    or evidence.effective_palette.requested_frame_number
                    != request.palette_frame_number
                )
            )
            or (
                (request.method != "bilinear" or evidence.color_mode != "indexed")
                and evidence.effective_palette is not None
            )
        ):
            raise _postcondition(
                invocation, "Image size, method, target, or Palette basis disagrees"
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
        return ImageResizeResult.model_validate(
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
)
