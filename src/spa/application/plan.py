"""Bounded, single-Sprite Operation Plan preflight and execution."""

from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any, Literal, assert_never

from pydantic import Field, ValidationError, model_validator

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.color.profile import (
    PROFILE_FILE_RESOURCE,
    PROFILE_ICC_RESOURCES,
    PROFILE_OPERATIONS,
    PROFILE_RESOURCE,
    AssignProfileInput,
    ConvertProfileInput,
    ProfileEvidence,
    profile_payload,
    reject_profile,
    validate_profile_evidence,
)
from spa.authoring.document.cel import (
    CEL_OPERATIONS,
    CEL_SELECT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    CelAddInput,
    CelFrameRangeDetails,
    CelState,
    CelTargetDetails,
    validate_added_cel,
)
from spa.authoring.document.cel import (
    CelAddress as LifecycleCelAddress,
)
from spa.authoring.document.cel_relationship import (
    CEL_RELATIONSHIP_OPERATIONS,
    CEL_RELATIONSHIP_RESOURCE,
    CelRelationshipChangeEvidence,
    CelSetInput,
    validate_relationship_evidence,
)
from spa.authoring.document.frame import (
    FRAME_OPERATIONS,
    FRAME_SUPPORT_RESOURCE,
    FrameAddInput,
    FrameDuplicateInput,
    FrameMutationEvidence,
    validate_frame_evidence,
    validate_frame_get_result,
    validate_frame_sequence,
)
from spa.authoring.document.layer import (
    LAYER_ADDRESS_FAILURE_CODES,
    LayerAddress,
    LayerTargetDetails,
)
from spa.authoring.document.motion import (
    MOTION_OPERATIONS,
    MOTION_RESOURCE,
    MotionEvidence,
    MotionInput,
    reject_motion,
    validate_motion_evidence,
)
from spa.authoring.document.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_CREATION_RESOURCE,
    SPRITE_INSPECTION_FIXTURE,
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_OPERATIONS,
    SPRITE_PERSISTENCE_RESOURCE,
    FrameFacts,
    InitialLayer,
    InspectionScope,
    SpriteCreateInput,
    SpriteCreateRequest,
    SpriteGetInput,
    SpriteGetRequest,
    SpriteInspection,
    SpriteMetadata,
    validate_created_sprite,
    validated_scope,
)
from spa.authoring.raster.paint import (
    PAINT_OPERATIONS,
    PAINT_PROBE_FIXTURE,
    PAINT_SUPPORT_RESOURCE,
    RASTER_COLOR_RESOURCE,
    PaintApplyEvidence,
    PaintApplyInput,
    validate_paint_evidence,
)
from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import (
    TargetCommit,
    source_target_identity_issue,
    validate_native_sprite_path,
)
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PostconditionEvidence,
    RequestIssue,
    ResponseEvidence,
    RuntimeIssue,
    TargetCommitEvidence,
)
from spa.contracts.public import (
    PublicModel,
    Request,
    RuntimeRequest,
    RuntimeRequirements,
    ValidationIssue,
)
from spa.contracts.raster import SELECTION_MASK_RESOURCE
from spa.contracts.rounding import ROUNDING_RESOURCE

MAX_PLAN_STEPS = 64
ELIGIBLE_OPERATIONS = {
    descriptor.name: descriptor
    for descriptor in (
        *SPRITE_OPERATIONS,
        *PROFILE_OPERATIONS,
        *PAINT_OPERATIONS,
        *FRAME_OPERATIONS,
        *CEL_OPERATIONS,
        *CEL_RELATIONSHIP_OPERATIONS,
        *MOTION_OPERATIONS,
    )
    if descriptor.plan_eligible
}
PLAN_RUN_HANDLER = PackagedHandler(
    "plan_run",
    "plan/plan_run.lua",
    (
        SPRITE_INSPECTION_RESOURCE,
        SPRITE_PERSISTENCE_RESOURCE,
        PROFILE_RESOURCE,
        PROFILE_FILE_RESOURCE,
        *PROFILE_ICC_RESOURCES,
        SPRITE_CREATION_RESOURCE,
        PAINT_SUPPORT_RESOURCE,
        RASTER_COLOR_RESOURCE,
        EFFECTIVE_PALETTE_RESOURCE,
        SELECTION_MASK_RESOURCE,
        FRAME_SUPPORT_RESOURCE,
        CEL_SUPPORT_RESOURCE,
        CEL_SELECT_RESOURCE,
        CEL_RELATIONSHIP_RESOURCE,
        MOTION_RESOURCE,
        ROUNDING_RESOURCE,
        DIGEST_RESOURCE,
        SPRITE_INSPECTION_FIXTURE,
        PAINT_PROBE_FIXTURE,
    ),
)


class CreateStep(PublicModel):
    operation: Literal["sprite create"]
    input: SpriteCreateInput


class GetStep(PublicModel):
    operation: Literal["sprite get"]
    input: SpriteGetInput


class PaintStep(PublicModel):
    operation: Literal["paint apply"]
    input: PaintApplyInput


class FrameListInput(PublicModel):
    pass


class FrameListStep(PublicModel):
    operation: Literal["frame list"]
    input: FrameListInput = Field(default_factory=FrameListInput)


class FrameGetInput(PublicModel):
    frame_number: int = Field(ge=1, strict=True)


class FrameGetStep(PublicModel):
    operation: Literal["frame get"]
    input: FrameGetInput


class FrameAddStep(PublicModel):
    operation: Literal["frame add"]
    input: FrameAddInput


class FrameDuplicateStep(PublicModel):
    operation: Literal["frame duplicate"]
    input: FrameDuplicateInput


class CelAddStep(PublicModel):
    operation: Literal["cel add"]
    input: CelAddInput


class CelSetStep(PublicModel):
    operation: Literal["cel set"]
    input: CelSetInput


class MotionStep(PublicModel):
    operation: Literal["motion apply"]
    input: MotionInput


class AssignProfileStep(PublicModel):
    operation: Literal["sprite assign-color-profile"]
    input: AssignProfileInput


class ConvertProfileStep(PublicModel):
    operation: Literal["sprite convert-color-profile"]
    input: ConvertProfileInput


PlanStep = Annotated[
    CreateStep
    | GetStep
    | PaintStep
    | FrameListStep
    | FrameGetStep
    | FrameAddStep
    | FrameDuplicateStep
    | CelAddStep
    | CelSetStep
    | MotionStep
    | AssignProfileStep
    | ConvertProfileStep,
    Field(discriminator="operation"),
]


class PlanPostconditions(PublicModel):
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    frame_count: int | None = Field(default=None, ge=1)
    color_mode: Literal["rgb", "grayscale", "indexed"] | None = None


class PlanDefinition(PublicModel):
    source_sprite_file: str | None = None
    target_sprite_file: str | None = None
    in_place: bool = False
    overwrite: bool = False
    steps: list[PlanStep] = Field(min_length=1, max_length=MAX_PLAN_STEPS)
    postconditions: PlanPostconditions = Field(default_factory=PlanPostconditions)

    @model_validator(mode="after")
    def validate_boundary(self) -> "PlanDefinition":
        if any(step.operation not in ELIGIBLE_OPERATIONS for step in self.steps):
            raise ValueError("Plan Step Operation is not declared Plan-eligible")
        create_indexes = [
            i for i, step in enumerate(self.steps) if step.operation == "sprite create"
        ]
        if create_indexes and create_indexes != [0]:
            raise ValueError("Sprite creation is allowed only as the first Plan Step")
        creates = bool(create_indexes)
        if creates:
            first = self.steps[0]
            assert isinstance(first, CreateStep)
            known = {
                "width": first.input.width,
                "height": first.input.height,
                "color_mode": first.input.color_mode,
                "frame_count": 1
                + sum(
                    isinstance(step, (FrameAddStep, FrameDuplicateStep))
                    for step in self.steps
                ),
            }
            for field, expected in self.postconditions.model_dump(
                exclude_none=True
            ).items():
                if expected != known[field]:
                    raise ValueError(
                        f"Plan {field} Postcondition contradicts Sprite creation"
                    )
        mutates = creates or any(
            isinstance(
                step,
                (
                    PaintStep,
                    FrameAddStep,
                    FrameDuplicateStep,
                    CelAddStep,
                    CelSetStep,
                    MotionStep,
                    AssignProfileStep,
                    ConvertProfileStep,
                ),
            )
            for step in self.steps
        )
        if (creates and self.source_sprite_file is not None) or (
            not creates and self.source_sprite_file is None
        ):
            raise ValueError(
                "Plan requires exactly one Source Sprite or first creation Step"
            )
        if mutates != (self.target_sprite_file is not None):
            raise ValueError(
                "Mutating Plan requires one Target Sprite File; read Plan has none"
            )
        for value in (self.source_sprite_file, self.target_sprite_file):
            if value is not None:
                validate_native_sprite_path(value)
        if creates or not mutates:
            if self.in_place:
                raise ValueError("In-place intent requires an existing Source Sprite")
        else:
            assert self.source_sprite_file is not None
            assert self.target_sprite_file is not None
            if self.in_place and not self.overwrite:
                raise ValueError("In-place Plan requires overwrite permission")
        if not mutates and self.overwrite:
            raise ValueError("Read Plan cannot request overwrite")
        return self

    @property
    def commit_required(self) -> bool:
        return self.target_sprite_file is not None


class PlanCheckRequest(Request):
    plan: PlanDefinition


class PlanCheckResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa plan check"] = "spa plan check"
    step_count: int = Field(ge=1)
    commit_required: bool


class PlanRunRequest(RuntimeRequest):
    plan: PlanDefinition


class CreateStepResult(PublicModel):
    sprite: SpriteInspection
    initial_layer: InitialLayer


class GetStepResult(PublicModel):
    sprite: SpriteInspection
    scope: InspectionScope


class PaintStepResult(PaintApplyEvidence):
    persisted_reopen_verified: Literal[False]


class FrameListStepResult(PublicModel):
    frames: list[FrameFacts]


class FrameGetStepResult(PublicModel):
    frame: FrameFacts


class FrameMutationStepResult(FrameMutationEvidence):
    persisted_reopen_verified: Literal[False]
    sprite: None = None


class CelAddStepResult(PublicModel):
    before: CelState
    before_cel_count: int = Field(ge=0)
    cel: CelState


class CelSetStepResult(CelRelationshipChangeEvidence):
    persisted_reopen_verified: Literal[False]


class MotionStepResult(MotionEvidence):
    persisted_reopen_verified: Literal[False]


class ProfileStepResult(ProfileEvidence):
    persisted_reopen_verified: Literal[False]


class AssignProfileStepOutcome(PublicModel):
    operation: Literal["sprite assign-color-profile"]
    result: ProfileStepResult


class ConvertProfileStepOutcome(PublicModel):
    operation: Literal["sprite convert-color-profile"]
    result: ProfileStepResult


class CreateStepOutcome(PublicModel):
    operation: Literal["sprite create"]
    result: CreateStepResult


class GetStepOutcome(PublicModel):
    operation: Literal["sprite get"]
    result: GetStepResult


class PaintStepOutcome(PublicModel):
    operation: Literal["paint apply"]
    result: PaintStepResult


class FrameListStepOutcome(PublicModel):
    operation: Literal["frame list"]
    result: FrameListStepResult


class FrameGetStepOutcome(PublicModel):
    operation: Literal["frame get"]
    result: FrameGetStepResult


class FrameAddStepOutcome(PublicModel):
    operation: Literal["frame add"]
    result: FrameMutationStepResult


class FrameDuplicateStepOutcome(PublicModel):
    operation: Literal["frame duplicate"]
    result: FrameMutationStepResult


class CelAddStepOutcome(PublicModel):
    operation: Literal["cel add"]
    result: CelAddStepResult


class CelSetStepOutcome(PublicModel):
    operation: Literal["cel set"]
    result: CelSetStepResult


class MotionStepOutcome(PublicModel):
    operation: Literal["motion apply"]
    result: MotionStepResult


StepOutcome = Annotated[
    CreateStepOutcome
    | GetStepOutcome
    | PaintStepOutcome
    | FrameListStepOutcome
    | FrameGetStepOutcome
    | FrameAddStepOutcome
    | FrameDuplicateStepOutcome
    | CelAddStepOutcome
    | CelSetStepOutcome
    | MotionStepOutcome
    | AssignProfileStepOutcome
    | ConvertProfileStepOutcome,
    Field(discriminator="operation"),
]


class PlanRunResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa plan run"] = "spa plan run"
    steps: list[StepOutcome] = Field(min_length=1, max_length=MAX_PLAN_STEPS)
    final_sprite: SpriteInspection
    persisted_reopen_verified: bool
    target_commit: TargetCommit | None


def check_plan(
    request: PlanCheckRequest, services: OperationServices
) -> PlanCheckResult:
    _preflight_paths(request.plan, services)
    _prepare_profile_inputs(request.plan, services)
    return PlanCheckResult(
        step_count=len(request.plan.steps), commit_required=request.plan.commit_required
    )


def _prepare_profile_inputs(
    plan: PlanDefinition, services: OperationServices
) -> dict[int, dict[str, Any]]:
    return {
        index: profile_payload(step.input, services, index)
        for index, step in enumerate(plan.steps, 1)
        if isinstance(step, (AssignProfileStep, ConvertProfileStep))
    }


def _preflight_paths(plan: PlanDefinition, services: OperationServices) -> None:
    if plan.source_sprite_file is not None:
        source = services.target_files.observe_path(Path(plan.source_sprite_file))
        if not source.is_file:
            raise RequestIssue(
                [
                    ValidationIssue(
                        location=["plan", "source_sprite_file"],
                        code="source_not_file",
                        message="Source Sprite File does not exist as a regular file",
                    )
                ]
            )
    if plan.target_sprite_file is not None:
        target = services.target_files.observe_path(Path(plan.target_sprite_file))
        reason = None
        if not target.parent_is_dir:
            reason = "Target Sprite File parent directory does not exist"
        elif target.exists and not target.is_file:
            reason = "Target Sprite File is not a regular file"
        elif target.exists and not plan.overwrite:
            reason = "Target Sprite File exists and overwrite is false"
        if reason is not None:
            raise RequestIssue(
                [
                    ValidationIssue(
                        location=["plan", "target_sprite_file"],
                        code="target_not_writable",
                        message=reason,
                    )
                ]
            )
    if plan.source_sprite_file is not None and plan.target_sprite_file is not None:
        identity_issue = source_target_identity_issue(
            services.target_files,
            Path(plan.source_sprite_file),
            Path(plan.target_sprite_file),
            plan.in_place,
        )
        if identity_issue is not None:
            raise RequestIssue(
                [
                    ValidationIssue(
                        location=["plan", *identity_issue.location],
                        code=identity_issue.code,
                        message=identity_issue.message,
                    )
                ]
            )


def _malformed(
    invocation: KernelInvocationResult,
    reason: str,
    *,
    failed_step: int | None = None,
    failed_operation: str | None = None,
) -> RuntimeIssue:
    return RuntimeIssue(
        "response_malformed",
        reason,
        ResponseEvidence(
            response_path=invocation.response_path,
            failed_step=failed_step,
            failed_operation=failed_operation,
        ),
        invocation.diagnostics,
    )


def _postcondition(
    invocation: KernelInvocationResult,
    reason: str,
    *,
    failed_step: int | None = None,
    failed_operation: str | None = None,
) -> RuntimeIssue:
    return RuntimeIssue(
        "postcondition_failed",
        reason,
        PostconditionEvidence(
            response_path=invocation.response_path,
            reason=reason,
            failed_step=failed_step,
            failed_operation=failed_operation,
        ),
        invocation.diagnostics,
    )


def _combined_requirements(operations: list[str]) -> RuntimeRequirements:
    requirements = [
        ELIGIBLE_OPERATIONS[operation].runtime_requirements for operation in operations
    ]
    assert all(item is not None for item in requirements)
    versions = {item.lua_language for item in requirements if item is not None}
    if len(versions) != 1:
        raise ValueError("Plan Step Operations require incompatible Lua languages")
    return RuntimeRequirements(
        lua_language=versions.pop(),
        minimum_api_version=max(
            item.minimum_api_version for item in requirements if item is not None
        ),
        required_capabilities=list(
            dict.fromkeys(
                capability
                for item in requirements
                if item is not None
                for capability in item.required_capabilities
            )
        ),
    )


def _requirements(plan: PlanDefinition) -> RuntimeRequirements:
    return _combined_requirements(
        ["sprite get", *(step.operation for step in plan.steps)]
    )


PLAN_DISCOVERY_REQUIREMENTS = _combined_requirements(list(ELIGIBLE_OPERATIONS))


def _validated_steps(
    request: PlanRunRequest,
    invocation: KernelInvocationResult,
    canvas: SpriteMetadata,
    profile_inputs: dict[int, dict[str, Any]],
) -> list[StepOutcome]:
    raw = invocation.payload.get("steps")
    if not isinstance(raw, list) or len(raw) != len(request.plan.steps):
        missing_index = (
            len(raw) + 1
            if isinstance(raw, list) and len(raw) < len(request.plan.steps)
            else None
        )
        raise _malformed(
            invocation,
            "Plan Kernel returned an incomplete Step sequence",
            failed_step=missing_index,
            failed_operation=(
                request.plan.steps[missing_index - 1].operation
                if missing_index is not None
                else None
            ),
        )
    outcomes: list[StepOutcome] = []
    for index, (step, item) in enumerate(zip(request.plan.steps, raw, strict=True), 1):
        if not isinstance(item, dict) or item.get("operation") != step.operation:
            raise _malformed(
                invocation,
                "Plan Kernel returned a mismatched Step Operation",
                failed_step=index,
                failed_operation=step.operation,
            )
        try:
            if isinstance(step, CreateStep):
                outcome: StepOutcome = CreateStepOutcome.model_validate(item)
            elif isinstance(step, GetStep):
                sprite = SpriteInspection.model_validate(item["result"]["sprite"])
                scope_request = SpriteGetRequest(
                    sprite_file=request.plan.source_sprite_file
                    or request.plan.target_sprite_file
                    or "plan.aseprite",
                    inspection_scope=step.input.inspection_scope,
                )
                scope = validated_scope(scope_request, sprite, invocation)
                outcome = GetStepOutcome(
                    operation="sprite get",
                    result=GetStepResult(sprite=sprite, scope=scope),
                )
            elif isinstance(step, PaintStep):
                outcome = PaintStepOutcome.model_validate(item)
                validate_paint_evidence(step.input, outcome.result, invocation)
            elif isinstance(step, FrameListStep):
                result = item["result"]
                count = result["frame_count"]
                if type(count) is not int or count < 1:
                    raise ValueError("Frame List has invalid Frame count")
                frames = [
                    FrameFacts.model_validate(value) for value in result["frames"]
                ]
                validate_frame_sequence(frames, count, invocation)
                outcome = FrameListStepOutcome(
                    operation="frame list", result=FrameListStepResult(frames=frames)
                )
            elif isinstance(step, FrameGetStep):
                frame = validate_frame_get_result(
                    item["result"],
                    step.input.frame_number,
                    invocation,
                    ["plan", "steps", index - 1, "input", "frame_number"],
                )
                outcome = FrameGetStepOutcome(
                    operation="frame get", result=FrameGetStepResult(frame=frame)
                )
            elif isinstance(step, FrameAddStep):
                outcome = FrameAddStepOutcome.model_validate(item)
                validate_frame_evidence(step.input, outcome.result, invocation)
            elif isinstance(step, CelSetStep):
                outcome = CelSetStepOutcome.model_validate(item)
                validate_relationship_evidence(
                    step.input, outcome.result, invocation, "set"
                )
            elif isinstance(step, MotionStep):
                outcome = MotionStepOutcome.model_validate(item)
                validate_motion_evidence(step.input, outcome.result, invocation)
            elif isinstance(step, ConvertProfileStep):
                outcome = ConvertProfileStepOutcome.model_validate(item)
                validate_profile_evidence(
                    step.input, outcome.result, invocation, profile_inputs[index]
                )
            elif isinstance(step, AssignProfileStep):
                outcome = AssignProfileStepOutcome.model_validate(item)
                validate_profile_evidence(
                    step.input, outcome.result, invocation, profile_inputs[index]
                )
            elif isinstance(step, CelAddStep):
                outcome = CelAddStepOutcome.model_validate(item)
                target = step.input.target
                before, after = outcome.result.before, outcome.result.cel
                validate_added_cel(step.input, after, canvas, invocation)
                if (
                    before.exists
                    or before.frame_number != target.frame_number
                    or after.frame_number != target.frame_number
                    or before.layer_path != after.layer_path
                    or (
                        target.layer.layer_path is not None
                        and after.layer_path != target.layer.layer_path
                    )
                ):
                    raise ValueError("Cel add Step evidence differs from its target")
            else:
                assert isinstance(step, FrameDuplicateStep)
                outcome = FrameDuplicateStepOutcome.model_validate(item)
                validate_frame_evidence(step.input, outcome.result, invocation)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise _malformed(
                invocation,
                "Plan Kernel returned invalid Step evidence",
                failed_step=index,
                failed_operation=step.operation,
            ) from exc
        except RuntimeIssue as exc:
            raise _postcondition(
                invocation,
                str(exc),
                failed_step=index,
                failed_operation=step.operation,
            ) from exc
        outcomes.append(outcome)
    return outcomes


def _validate_cel_count_sequence(
    outcomes: list[StepOutcome],
    final_sprite: SpriteInspection,
    invocation: KernelInvocationResult,
) -> None:
    """Reconcile live Step counts with the final Sprite and validated Cel deltas."""
    cel_count = final_sprite.metadata.cel_count
    for index in range(len(outcomes) - 1, -1, -1):
        outcome = outcomes[index]
        reported_count = None
        if isinstance(outcome, (CreateStepOutcome, GetStepOutcome)):
            reported_count = outcome.result.sprite.metadata.cel_count
        elif isinstance(outcome, CelAddStepOutcome):
            cel_count -= 1
            reported_count = outcome.result.before_cel_count
        elif isinstance(outcome, (CelSetStepOutcome, MotionStepOutcome)):
            reported_count = outcome.result.before_cel_count
        elif isinstance(outcome, (FrameAddStepOutcome, FrameDuplicateStepOutcome)):
            # Both copied and linked Images add one Cel per inserted Layer/Frame.
            cel_count -= outcome.result.inserted_cel_count
        elif isinstance(
            outcome,
            (
                PaintStepOutcome,
                FrameListStepOutcome,
                FrameGetStepOutcome,
                AssignProfileStepOutcome,
                ConvertProfileStepOutcome,
            ),
        ):
            pass
        else:
            assert_never(outcome)
        if cel_count < 0 or (
            reported_count is not None and reported_count != cel_count
        ):
            raise _malformed(
                invocation,
                "Plan Step Cel count contradicts the final Sprite and Step changes",
                failed_step=index + 1,
                failed_operation=outcome.operation,
            )


def run_plan(request: PlanRunRequest, services: OperationServices) -> PlanRunResult:
    if services.invoke_kernel_direct is None:
        raise TypeError("Plan run requires the direct Kernel invocation adapter")
    plan = request.plan
    _preflight_paths(plan, services)
    profile_inputs = _prepare_profile_inputs(plan, services)
    staged = (
        services.target_files.staged_path(Path(plan.target_sprite_file))
        if plan.target_sprite_file is not None
        else None
    )
    payload: dict[str, Any] = {
        "source_sprite_file": plan.source_sprite_file,
        "staged_sprite_file": str(staged) if staged is not None else None,
        "steps": [
            step.model_dump(mode="json", exclude_none=True) for step in plan.steps
        ],
        "postconditions": plan.postconditions.model_dump(
            mode="json", exclude_none=True
        ),
        "runtime_requirements": _requirements(plan).model_dump(mode="json"),
    }
    for index, prepared in profile_inputs.items():
        payload["steps"][index - 1]["input"] = prepared
    try:
        invocation = services.invoke_kernel_direct(
            request, PLAN_RUN_HANDLER, payload, request.timeout_seconds
        )
        profile_rejection = invocation.payload.get("profile_rejection")
        if profile_rejection is not None:
            index = (
                profile_rejection.get("step_number")
                if isinstance(profile_rejection, dict)
                else None
            )
            if type(index) is not int or index not in profile_inputs:
                raise _malformed(invocation, "Invalid Color Profile Step rejection")
            reject_profile(
                replace(
                    invocation, payload={"rejection": profile_rejection["rejection"]}
                ),
                index,
            )
        cel_rejection = invocation.payload.get("cel_rejection")
        if cel_rejection is not None:
            if not isinstance(cel_rejection, dict):
                raise _malformed(
                    invocation, "Plan Kernel returned invalid Cel rejection"
                )
            index = cel_rejection.get("step_number")
            if type(index) is not int or index < 1 or index > len(plan.steps):
                raise _malformed(
                    invocation, "Plan Kernel returned invalid Cel rejection"
                )
            step = plan.steps[index - 1]
            if isinstance(step, MotionStep):
                try:
                    reject_motion(
                        step.input,
                        replace(invocation, payload={"rejection": cel_rejection}),
                    )
                except OperationIssue as exc:
                    raise OperationIssue(
                        exc.code,
                        str(exc),
                        exc.details.model_copy(update={"step_number": index}),
                    ) from exc
                except RuntimeIssue as exc:
                    raise _malformed(
                        invocation,
                        str(exc),
                        failed_step=index,
                        failed_operation=step.operation,
                    ) from exc
            code = cel_rejection.get("code")
            message = cel_rejection.get("message")
            add_codes = {
                *LAYER_ADDRESS_FAILURE_CODES,
                "cel_already_exists",
                "cel_unsupported_target",
                "cel_frame_out_of_bounds",
            }
            set_codes = {
                *LAYER_ADDRESS_FAILURE_CODES,
                "cel_not_found",
                "cel_unsupported_target",
                "cel_frame_out_of_bounds",
            }
            if (
                not isinstance(code, str)
                or not isinstance(message, str)
                or not (
                    (isinstance(step, CelAddStep) and code in add_codes)
                    or (isinstance(step, CelSetStep) and code in set_codes)
                    or (isinstance(step, PaintStep) and code == "cel_not_found")
                )
            ):
                raise _malformed(
                    invocation, "Plan Kernel returned invalid Cel rejection"
                )
            if (
                isinstance(step, (CelAddStep, CelSetStep))
                and code in LAYER_ADDRESS_FAILURE_CODES
            ):
                details = LayerTargetDetails(
                    address_role="target",
                    address=step.input.target.layer,
                    step_number=index,
                )
            elif (
                isinstance(step, (CelAddStep, CelSetStep))
                and code == "cel_frame_out_of_bounds"
            ):
                details = CelFrameRangeDetails(
                    from_frame=step.input.target.frame_number,
                    to_frame=step.input.target.frame_number,
                    step_number=index,
                )
            else:
                target = (
                    step.input.target
                    if isinstance(step, (CelAddStep, CelSetStep))
                    else LifecycleCelAddress(
                        layer=LayerAddress(layer_path=step.input.target.layer_path),
                        frame_number=step.input.target.frame_number,
                    )
                )
                details = CelTargetDetails(target=target, step_number=index)
            raise OperationIssue(code, message, details)
        rejection = invocation.payload.get("frame_get_rejection")
        if rejection is not None:
            index = (
                rejection.get("step_number") if isinstance(rejection, dict) else None
            )
            if (
                type(index) is not int
                or index < 1
                or index > len(plan.steps)
                or not isinstance(plan.steps[index - 1], FrameGetStep)
            ):
                raise _malformed(
                    invocation, "Plan Kernel returned invalid Frame rejection"
                )
            step = plan.steps[index - 1]
            assert isinstance(step, FrameGetStep)
            try:
                validate_frame_get_result(
                    rejection["result"],
                    step.input.frame_number,
                    invocation,
                    ["plan", "steps", index - 1, "input", "frame_number"],
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise _malformed(
                    invocation,
                    "Plan Kernel returned invalid Frame rejection",
                    failed_step=index,
                    failed_operation="frame get",
                ) from exc
            except RuntimeIssue as exc:
                raise _postcondition(
                    invocation,
                    str(exc),
                    failed_step=index,
                    failed_operation="frame get",
                ) from exc
            raise _malformed(
                invocation,
                "Plan Kernel rejected an existing Frame",
                failed_step=index,
                failed_operation="frame get",
            )
        try:
            final_sprite = SpriteInspection.model_validate(
                invocation.payload["final_sprite"]
            )
            persisted = invocation.payload["persisted_reopen_verified"]
            if type(persisted) is not bool or persisted != plan.commit_required:
                raise ValueError("Plan persistence flag differs from commit intent")
        except (KeyError, TypeError, ValidationError, ValueError) as exc:
            raise _malformed(
                invocation, "Plan Kernel returned invalid final Sprite evidence"
            ) from exc
        final_scope_request = SpriteGetRequest(
            sprite_file=plan.target_sprite_file
            or plan.source_sprite_file
            or "plan.aseprite",
            inspection_scope=list(INSPECTION_SECTIONS),
        )
        validated_scope(final_scope_request, final_sprite, invocation)
        # Eligible Steps keep the Canvas size; Add receipts describe their own
        # initial state, even when a later Step paints or moves that Cel.
        outcomes = _validated_steps(
            request, invocation, final_sprite.metadata, profile_inputs
        )
        metadata = final_sprite.metadata
        for field, expected in plan.postconditions.model_dump(
            exclude_none=True
        ).items():
            if getattr(metadata, field) != expected:
                raise _postcondition(invocation, f"Plan {field} Postcondition failed")
        if isinstance(plan.steps[0], CreateStep):
            first = outcomes[0]
            assert isinstance(first, CreateStepOutcome)
            create = plan.steps[0].input
            create_request = SpriteCreateRequest(
                target_sprite_file=plan.target_sprite_file or "plan.aseprite",
                overwrite=plan.overwrite,
                **create.model_dump(),
            )
            try:
                validate_created_sprite(
                    create_request,
                    first.result.sprite,
                    first.result.initial_layer,
                    invocation,
                )
            except RuntimeIssue as exc:
                raise _postcondition(
                    invocation,
                    str(exc),
                    failed_step=1,
                    failed_operation="sprite create",
                ) from exc
        _validate_cel_count_sequence(outcomes, final_sprite, invocation)
        target_commit = None
        if staged is not None:
            assert plan.target_sprite_file is not None
            if plan.source_sprite_file is not None:
                identity_issue = source_target_identity_issue(
                    services.target_files,
                    Path(plan.source_sprite_file),
                    Path(plan.target_sprite_file),
                    plan.in_place,
                )
                if identity_issue is not None:
                    raise RuntimeIssue(
                        "target_commit_failed",
                        "Source/Target publication identity changed before Target Commit",
                        TargetCommitEvidence(
                            plan.target_sprite_file, "source_target_identity_changed"
                        ),
                    )
            committed = services.target_files.commit(
                staged, Path(plan.target_sprite_file), overwrite=plan.overwrite
            )
            target_commit = TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            )
        return PlanRunResult(
            steps=outcomes,
            final_sprite=final_sprite,
            persisted_reopen_verified=persisted,
            target_commit=target_commit,
        )
    finally:
        if staged is not None:
            services.target_files.discard(staged)


PLAN_OPERATIONS = (
    OperationDescriptor(
        "plan check",
        PlanCheckRequest,
        PlanCheckResult,
        check_plan,
        lambda result: f"Plan accepted: {result.step_count} Steps",
        None,
        ("invalid_request", "color_profile_file_failed", "resource_incomplete"),
    ),
    OperationDescriptor(
        "plan run",
        PlanRunRequest,
        PlanRunResult,
        run_plan,
        lambda result: (
            result.target_commit.target_sprite_file
            if result.target_commit is not None
            else f"Plan completed: {len(result.steps)} Steps"
        ),
        PLAN_DISCOVERY_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            *LAYER_ADDRESS_FAILURE_CODES,
            "cel_already_exists",
            "cel_not_found",
            "cel_unsupported_target",
            "cel_frame_out_of_bounds",
            "color_profile_file_failed",
            "color_profile_source_unsupported",
            "motion_linked_cel",
            "motion_position_out_of_bounds",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes one Target Sprite File for a mutating Plan",),
        probe_before_execute=False,
    ),
)
