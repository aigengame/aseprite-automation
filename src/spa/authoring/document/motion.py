"""Bounded position and opacity authoring over existing per-Frame Cels."""

from itertools import pairwise
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, ValidationError, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.document.cel import (
    CEL_SELECT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    CelAddress,
    CelState,
    CelTargetDetails,
    raise_cel_rejection,
)
from spa.authoring.document.cel_relationship import CelRelationshipRequest
from spa.authoring.document.layer import LAYER_ADDRESS_FAILURE_CODES, LayerAddress
from spa.authoring.document.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteGetRequest,
    SpriteInspection,
    validated_scope,
)
from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import TargetCommit
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
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequirements
from spa.contracts.rounding import ROUNDING_RESOURCE, Rounding

Interpolation = Literal["step", "linear", "smoothstep"]


class PositionOffset(PublicModel):
    x: int = Field(ge=-65535, le=65535, strict=True)
    y: int = Field(ge=-65535, le=65535, strict=True)


class PositionKey(PublicModel):
    frame_number: int = Field(ge=1, strict=True)
    offset: PositionOffset


class OpacityKey(PublicModel):
    frame_number: int = Field(ge=1, strict=True)
    opacity: int = Field(ge=0, le=255, strict=True)


class PositionCurve(PublicModel):
    interpolation: Interpolation
    rounding: Rounding
    keys: list[PositionKey] = Field(min_length=1)


class OpacityCurve(PublicModel):
    interpolation: Interpolation
    rounding: Rounding
    keys: list[OpacityKey] = Field(min_length=1)


class MotionInput(PublicModel):
    layer: LayerAddress
    from_frame: int = Field(ge=1, strict=True)
    to_frame: int = Field(ge=1, strict=True)
    position_offsets: PositionCurve | None = None
    opacity: OpacityCurve | None = None

    @model_validator(mode="after")
    def validate_curves(self) -> Self:
        if self.from_frame > self.to_frame:
            raise ValueError("Frame Range must be ordered")
        if self.position_offsets is None and self.opacity is None:
            raise ValueError("Specify position_offsets, opacity, or both")
        for curve in (self.position_offsets, self.opacity):
            if curve is None:
                continue
            numbers = [key.frame_number for key in curve.keys]
            if (
                numbers[0] != self.from_frame
                or numbers[-1] != self.to_frame
                or any(left >= right for left, right in pairwise(numbers))
            ):
                raise ValueError(
                    "Curve keys must increase strictly and cover both Frame Range endpoints"
                )
        return self


class MotionRequest(CelRelationshipRequest, MotionInput):
    pass


class CelMotion(PublicModel):
    before: CelState
    after: CelState
    offset: PositionOffset | None


class MotionEvidence(PublicModel):
    before_cel_count: int = Field(ge=0)
    cels: list[CelMotion] = Field(min_length=1)
    unchanged_facts_verified: Literal[True]


class MotionResult(MotionEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa motion apply"] = "spa motion apply"
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]
    target_commit: TargetCommit


MOTION_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "motion_linked_cel",
        "Motion requires independent Cel Images",
        "input",
        CelTargetDetails,
    ),
    FailureCodeSpec(
        "motion_position_out_of_bounds",
        "Sampled Cel position is outside signed 16-bit coordinates",
        "input",
        CelTargetDetails,
    ),
)
MOTION_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    *LAYER_ADDRESS_FAILURE_CODES,
    "cel_frame_out_of_bounds",
    "cel_unsupported_target",
    "cel_not_found",
    "motion_linked_cel",
    "motion_position_out_of_bounds",
    "target_commit_failed",
)
MOTION_RESOURCE = PackagedResource("motion", "document/animation/motion_support.lua")
MOTION_RESOURCES = (
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_PERSISTENCE_RESOURCE,
    CEL_SELECT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    ROUNDING_RESOURCE,
    DIGEST_RESOURCE,
    MOTION_RESOURCE,
)
MOTION_HANDLER = PackagedHandler(
    "motion_apply", "document/animation/motion_apply.lua", MOTION_RESOURCES
)
MOTION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_cel_relationships", "aseprite_sprite_inspection"],
)


def reject_motion(input: MotionInput, invocation: KernelInvocationResult) -> None:
    rejected = invocation.payload.get("rejection")
    if rejected is None:
        return
    if not isinstance(rejected, dict):
        raise _invalid(invocation, "Motion rejection is not an object")
    if rejected.get("code") not in {
        *LAYER_ADDRESS_FAILURE_CODES,
        "cel_frame_out_of_bounds",
        "cel_unsupported_target",
        "cel_not_found",
        "motion_linked_cel",
        "motion_position_out_of_bounds",
    }:
        raise _invalid(invocation, "Motion rejection has an unsupported code")
    number = rejected.get("frame_number", input.from_frame)
    if type(number) is not int or not input.from_frame <= number <= input.to_frame:
        raise _invalid(invocation, "Motion rejection has an invalid Frame Number")
    target = CelAddress(layer=input.layer, frame_number=number)
    if rejected.get("code") in {spec.code for spec in MOTION_FAILURE_CODE_SPECS}:
        if not isinstance(rejected.get("message"), str):
            raise _invalid(invocation, "Motion rejection has no message")
        raise OperationIssue(
            rejected["code"], rejected["message"], CelTargetDetails(target=target)
        )
    raise_cel_rejection(
        invocation, input.layer, target, (input.from_frame, input.to_frame)
    )


def _invalid(invocation: KernelInvocationResult, reason: str) -> RuntimeIssue:
    return RuntimeIssue(
        "response_malformed",
        reason,
        ResponseEvidence(response_path=invocation.response_path),
        invocation.diagnostics,
    )


def validate_motion_evidence(
    input: MotionInput, evidence: MotionEvidence, invocation: KernelInvocationResult
) -> None:
    if len(
        evidence.cels
    ) != input.to_frame - input.from_frame + 1 or evidence.before_cel_count < len(
        evidence.cels
    ):
        raise _invalid(invocation, "Motion evidence has incomplete Cel coverage")
    selected_path = input.layer.layer_path or evidence.cels[0].before.layer_path
    position_keys = (
        {key.frame_number: key.offset for key in input.position_offsets.keys}
        if input.position_offsets
        else {}
    )
    opacity_keys = (
        {key.frame_number: key.opacity for key in input.opacity.keys}
        if input.opacity
        else {}
    )
    for number, change in enumerate(evidence.cels, input.from_frame):
        before, after = change.before, change.after
        if any(
            not fact.exists
            or fact.frame_number != number
            or fact.layer_path != selected_path
            or fact.is_background
            or fact.is_tilemap
            or fact.linked_cels
            for fact in (before, after)
        ):
            raise _invalid(
                invocation, "Motion evidence differs from the independent Cel targets"
            )
        assert (
            before.position
            and after.position
            and before.image_bounds
            and after.image_bounds
        )
        if (
            after.z_index != before.z_index
            or after.content != before.content
            or after.image_bounds.width != before.image_bounds.width
            or after.image_bounds.height != before.image_bounds.height
            or after.image_bounds.x != after.position.x
            or after.image_bounds.y != after.position.y
            or not -32768 <= after.position.x <= 32767
            or not -32768 <= after.position.y <= 32767
        ):
            raise _invalid(invocation, "Motion evidence changed preserved Cel facts")
        if input.position_offsets is None:
            valid_position = change.offset is None and after.position == before.position
        else:
            valid_position = (
                change.offset is not None
                and after.position.x == before.position.x + change.offset.x
                and after.position.y == before.position.y + change.offset.y
                and (
                    number not in position_keys
                    or change.offset == position_keys[number]
                )
            )
        if (
            not valid_position
            or (input.opacity is None and before.opacity != after.opacity)
            or (number in opacity_keys and after.opacity != opacity_keys[number])
        ):
            raise _invalid(
                invocation, "Motion evidence differs from the declared curves"
            )


def apply_motion(request: MotionRequest, services: OperationServices) -> MotionResult:
    source, target = Path(request.source_sprite_file), Path(request.target_sprite_file)
    completion = prepare_mutation(
        services.target_files,
        source,
        target,
        in_place=request.in_place,
        overwrite=request.overwrite,
        identity_change_message=("Source/Target identity changed before Target Commit"),
    )
    observation = services.probe_runtime(request)
    with completion as mutation:
        payload = request.model_dump(
            include=set(MotionInput.model_fields), exclude_none=True, mode="json"
        )
        payload.update(
            source_sprite_file=str(source),
            staged_sprite_file=str(mutation.staged_sprite_file),
        )
        invocation = services.invoke_kernel(
            observation, MOTION_HANDLER, payload, request.timeout_seconds
        )
        reject_motion(request, invocation)
        try:
            evidence = MotionEvidence.model_validate(
                {key: invocation.payload[key] for key in MotionEvidence.model_fields}
            )
            sprite = SpriteInspection.model_validate(invocation.payload["sprite"])
            if invocation.payload["persisted_reopen_verified"] is not True:
                raise ValueError("Motion persistence was not verified")
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise _invalid(
                invocation, "Motion handler returned invalid evidence"
            ) from exc
        validated_scope(
            SpriteGetRequest(
                sprite_file=str(target), inspection_scope=list(INSPECTION_SECTIONS)
            ),
            sprite,
            invocation,
        )
        validate_motion_evidence(request, evidence, invocation)
        if sprite.metadata.cel_count != evidence.before_cel_count:
            raise _invalid(invocation, "Motion changed the Cel count")
        committed = mutation.commit()
        return MotionResult(
            **evidence.model_dump(),
            sprite=sprite,
            persisted_reopen_verified=True,
            target_commit=committed,
        )


MOTION_OPERATIONS = (
    OperationDescriptor(
        "motion apply",
        MotionRequest,
        MotionResult,
        apply_motion,
        lambda result: result.target_commit.target_sprite_file,
        MOTION_REQUIREMENTS,
        MOTION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        plan_eligible=True,
    ),
)
