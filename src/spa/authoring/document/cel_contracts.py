"""Shared Cel requests, observed state, and native failure translation."""

from typing import Literal

from pydantic import Field, field_validator, model_validator

from spa.authoring.document.targets import (
    LAYER_ADDRESS_FAILURE_CODES,
    CelAddress,
    LayerAddress,
    LayerTargetDetails,
)
from spa.contracts.mutation import (
    require_overwrite_for_in_place,
    validate_native_sprite_path,
)
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationIssue,
    PackagedResource,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequest
from spa.contracts.raster import Point, Rectangle


class CelTargetInput(PublicModel):
    target: CelAddress


class CelMutationRequest(RuntimeRequest, CelTargetInput):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_commit_intent(self) -> "CelMutationRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class CelLink(PublicModel):
    layer_path: list[int] = Field(min_length=1)
    frame_number: int = Field(ge=1, strict=True)


class CelState(PublicModel):
    layer_path: list[int] = Field(min_length=1)
    frame_number: int = Field(ge=1, strict=True)
    exists: bool
    content: Literal["absent", "transparent", "nonempty"]
    is_background: bool
    is_tilemap: bool
    position: Point | None
    image_bounds: Rectangle | None
    opacity: int | None = Field(ge=0, le=255)
    z_index: int | None
    linked_cels: list[CelLink]

    @model_validator(mode="after")
    def validate_existence(self) -> "CelState":
        facts = (self.position, self.opacity, self.z_index)
        if (
            self.exists != (self.content != "absent")
            or (
                self.exists
                and (
                    any(value is None for value in facts)
                    or (self.image_bounds is None) != self.is_tilemap
                )
            )
            or (
                not self.exists
                and (
                    any(value is not None for value in facts)
                    or self.image_bounds is not None
                    or self.linked_cels
                )
            )
        ):
            raise ValueError("Cel existence contradicts Image or placement facts")
        return self


class CelTargetDetails(PublicModel):
    kind: Literal["cel_target"] = "cel_target"
    target: CelAddress
    step_number: int | None = Field(default=None, ge=1)


class CelFrameRangeDetails(PublicModel):
    kind: Literal["cel_frame_range"] = "cel_frame_range"
    from_frame: int = Field(ge=1)
    to_frame: int = Field(ge=1)
    step_number: int | None = Field(default=None, ge=1)


CEL_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "cel_already_exists",
        "The addressed Cel already exists",
        "input",
        CelTargetDetails,
    ),
    FailureCodeSpec(
        "cel_not_found",
        "The addressed Cel or Image does not exist",
        "input",
        CelTargetDetails,
    ),
    FailureCodeSpec(
        "cel_unsupported_target",
        "The Layer kind does not support the Cel operation",
        "input",
        CelTargetDetails,
    ),
    FailureCodeSpec(
        "cel_background_color_required",
        "Background clear requires an explicit Background Color",
        "input",
        CelTargetDetails,
    ),
    FailureCodeSpec(
        "cel_background_color_incompatible",
        "Background Color is incompatible with this Sprite",
        "input",
        CelTargetDetails,
    ),
    FailureCodeSpec(
        "cel_frame_out_of_bounds",
        "The Frame target is outside the Sprite timeline",
        "input",
        CelFrameRangeDetails,
    ),
)
CEL_FAILURE_CODES = tuple(spec.code for spec in CEL_FAILURE_CODE_SPECS)


CEL_SUPPORT_RESOURCE = PackagedResource("cel", "document/cel/cel_support.lua")


def raise_cel_rejection(
    invocation: KernelInvocationResult,
    layer: LayerAddress,
    target: CelAddress | None,
    frame_range: tuple[int, int],
    address_role: Literal["target", "source", "destination"] = "target",
) -> None:
    """Translate native Cel/Layer rejection facts for Document and raster callers.

    The caller supplies the addressed Layer, Cel, Frame Range, and address role.
    Unrecognized or malformed rejections remain Kernel response failures.
    """
    rejected = invocation.payload.get("rejection")
    if rejected is None:
        return
    if isinstance(rejected, dict) and isinstance(rejected.get("message"), str):
        code = rejected.get("code")
        if code in LAYER_ADDRESS_FAILURE_CODES:
            raise OperationIssue(
                code,
                rejected["message"],
                LayerTargetDetails(address_role=address_role, address=layer),
            )
        if code == "cel_frame_out_of_bounds":
            raise OperationIssue(
                code,
                rejected["message"],
                CelFrameRangeDetails(
                    from_frame=frame_range[0], to_frame=frame_range[1]
                ),
            )
        if code in CEL_FAILURE_CODES and target is not None:
            raise OperationIssue(
                code, rejected["message"], CelTargetDetails(target=target)
            )
    raise RuntimeIssue(
        "response_malformed",
        "Packaged handler returned an invalid rejection",
        ResponseEvidence(response_path=invocation.response_path),
        invocation.diagnostics,
    )
