"""Bounded, single-Sprite Operation Plan preflight and execution."""

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError, model_validator

from spa.contracts import (
    PublicModel,
    Request,
    RuntimeRequest,
    RuntimeRequirements,
    ValidationIssue,
)
from spa.mutation import TargetCommit, source_target_identity_issue
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.paint import (
    DIGEST_RESOURCE,
    PAINT_OPERATIONS,
    PAINT_PROBE_FIXTURE,
    PAINT_SUPPORT_RESOURCE,
    PaintApplyEvidence,
    PaintApplyInput,
    validate_paint_evidence,
)
from spa.ports import (
    KernelInvocationResult,
    OperationServices,
    PackagedHandler,
    PostconditionEvidence,
    RequestIssue,
    ResponseEvidence,
    RuntimeIssue,
    TargetCommitEvidence,
)
from spa.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_CREATION_RESOURCE,
    SPRITE_INSPECTION_FIXTURE,
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_OPERATIONS,
    InitialLayer,
    InspectionScope,
    SpriteCreateInput,
    SpriteCreateRequest,
    SpriteGetInput,
    SpriteGetRequest,
    SpriteInspection,
    validate_created_sprite,
    validated_scope,
)

MAX_PLAN_STEPS = 64
ELIGIBLE_OPERATIONS = {
    descriptor.name: descriptor
    for descriptor in (*SPRITE_OPERATIONS, *PAINT_OPERATIONS)
    if descriptor.plan_eligible
}
PLAN_RUN_HANDLER = PackagedHandler(
    "plan_run",
    (
        SPRITE_INSPECTION_RESOURCE,
        SPRITE_CREATION_RESOURCE,
        PAINT_SUPPORT_RESOURCE,
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


PlanStep = Annotated[CreateStep | GetStep | PaintStep, Field(discriminator="operation")]


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
                "frame_count": 1,
            }
            for field, expected in self.postconditions.model_dump(
                exclude_none=True
            ).items():
                if expected != known[field]:
                    raise ValueError(
                        f"Plan {field} Postcondition contradicts Sprite creation"
                    )
        mutates = creates or any(step.operation == "paint apply" for step in self.steps)
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
            if value is not None and Path(value).suffix.lower() != ".aseprite":
                raise ValueError("Sprite file must use the .aseprite extension")
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


class CreateStepOutcome(PublicModel):
    operation: Literal["sprite create"]
    result: CreateStepResult


class GetStepOutcome(PublicModel):
    operation: Literal["sprite get"]
    result: GetStepResult


class PaintStepOutcome(PublicModel):
    operation: Literal["paint apply"]
    result: PaintStepResult


StepOutcome = Annotated[
    CreateStepOutcome | GetStepOutcome | PaintStepOutcome,
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
    return PlanCheckResult(
        step_count=len(request.plan.steps), commit_required=request.plan.commit_required
    )


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
    request: PlanRunRequest, invocation: KernelInvocationResult
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
            else:
                outcome = PaintStepOutcome.model_validate(item)
                validate_paint_evidence(step.input, outcome.result, invocation)
        except (KeyError, TypeError, ValidationError) as exc:
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


def run_plan(request: PlanRunRequest, services: OperationServices) -> PlanRunResult:
    if services.invoke_kernel_direct is None:
        raise TypeError("Plan run requires the direct Kernel invocation adapter")
    plan = request.plan
    _preflight_paths(plan, services)
    staged = (
        services.target_files.staged_path(Path(plan.target_sprite_file))
        if plan.target_sprite_file is not None
        else None
    )
    payload: dict[str, Any] = {
        "source_sprite_file": plan.source_sprite_file,
        "staged_sprite_file": str(staged) if staged is not None else None,
        "steps": [step.model_dump(mode="json") for step in plan.steps],
        "postconditions": plan.postconditions.model_dump(
            mode="json", exclude_none=True
        ),
        "runtime_requirements": _requirements(plan).model_dump(mode="json"),
    }
    try:
        invocation = services.invoke_kernel_direct(
            request, PLAN_RUN_HANDLER, payload, request.timeout_seconds
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
        outcomes = _validated_steps(request, invocation)
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
                    create_request, final_sprite, first.result.initial_layer, invocation
                )
            except RuntimeIssue as exc:
                raise _postcondition(
                    invocation,
                    str(exc),
                    failed_step=1,
                    failed_operation="sprite create",
                ) from exc
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
        ("invalid_request",),
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
        (*RUNTIME_FAILURE_CODES, "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes one Target Sprite File for a mutating Plan",),
        probe_before_execute=False,
    ),
)
