"""Complete Image observation and replacement through canonical Raster values."""

from typing import Literal

from pydantic import Field, ValidationError, field_validator

from spa.cel import CEL_SUPPORT_RESOURCE, CelAddress, CelState, _reject
from spa.contracts import PublicModel, RuntimeRequest, RuntimeRequirements
from spa.layer import LAYER_ADDRESS_FAILURE_CODES, LAYER_SELECT_RESOURCE
from spa.mutation import validate_native_sprite_path
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.ports import (
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.raster import (
    RASTER_COLOR_RESOURCE,
    ColorValue,
    EffectivePaletteFact,
    PixelRegionSnapshot,
    PositiveRectangle,
    Size,
)
from spa.sprite import SPRITE_INSPECTION_RESOURCE


class IndividualImageSource(PublicModel):
    kind: Literal["individual"]
    target: CelAddress
    rectangle: PositiveRectangle


class ImageGetRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)
    source: IndividualImageSource

    _validate_source = field_validator("sprite_file")(validate_native_sprite_path)


class IndividualImageFacts(IndividualImageSource):
    coordinate_space: Literal["image-pixel"]
    layer_kind: Literal["transparent", "background", "reference"]
    image_size: Size
    associated_cels: list[CelState] = Field(min_length=1)


class ImageGetEvidence(PublicModel):
    source: IndividualImageFacts
    snapshot: PixelRegionSnapshot
    mask_color: ColorValue
    effective_palettes: list[EffectivePaletteFact]


class ImageGetResult(ImageGetEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image get"] = "spa image get"
    sprite_file: str


SNAPSHOT_RESOURCE = PackagedResource("image_snapshot", "image_snapshot.lua")
IMAGE_GET_HANDLER = PackagedHandler(
    "image_get",
    (
        SPRITE_INSPECTION_RESOURCE,
        LAYER_SELECT_RESOURCE,
        CEL_SUPPORT_RESOURCE,
        SNAPSHOT_RESOURCE,
        RASTER_COLOR_RESOURCE,
    ),
)
IMAGE_SNAPSHOT_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_cel_lifecycle", "aseprite_paint_apply"],
)


def get_image(request: ImageGetRequest, services: OperationServices) -> ImageGetResult:
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        IMAGE_GET_HANDLER,
        {
            "sprite_file": request.sprite_file,
            "source": request.source.model_dump(mode="json", exclude_none=True),
        },
        request.timeout_seconds,
    )
    target = request.source.target
    _reject(
        invocation, target.layer, target, (target.frame_number, target.frame_number)
    )
    try:
        evidence = ImageGetEvidence.model_validate(invocation.payload)
        if evidence.source.rectangle != request.source.rectangle:
            raise ValueError("Image Get source Rectangle differs from request")
    except (ValueError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            f"Invalid Image Get evidence: {exc}",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc
    return ImageGetResult(sprite_file=request.sprite_file, **evidence.model_dump())


IMAGE_SNAPSHOT_OPERATIONS = (
    OperationDescriptor(
        "image get",
        ImageGetRequest,
        ImageGetResult,
        get_image,
        lambda result: (
            f"{result.snapshot.rectangle.width} x {result.snapshot.rectangle.height}"
        ),
        IMAGE_SNAPSHOT_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "cel_not_found",
            "cel_unsupported_target",
            "cel_frame_out_of_bounds",
            *LAYER_ADDRESS_FAILURE_CODES,
        ),
    ),
)
