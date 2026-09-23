"""Bounded Operation Plan contracts and application orchestration."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from spa.contracts import PublicModel, Request
from spa.operation import OperationDescriptor
from spa.paint import CelAddress, PaintPixelPatch
from spa.ports import OperationServices
from spa.raster import SelectionApplication
from spa.sprite import INSPECTION_SECTIONS, InitialLayer, InspectionSection

MAX_PLAN_STEPS = 32


class CreateInput(PublicModel):
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)
    color_mode: Literal["rgb"]
    initial_layer: InitialLayer


class GetInput(PublicModel):
    inspection_scope: list[InspectionSection]

    @field_validator("inspection_scope")
    @classmethod
    def normalize_scope(cls, value: list[InspectionSection]) -> list[InspectionSection]:
        if len(value) != len(set(value)):
            raise ValueError("Inspection Scope cannot contain duplicate sections")
        requested = set(value)
        return [section for section in INSPECTION_SECTIONS if section in requested]


class PaintInput(PublicModel):
    target: CelAddress
    patch: PaintPixelPatch
    clipping: Literal["reject", "clip"] = "reject"
    selection: SelectionApplication | None = None

    @model_validator(mode="after")
    def bound_pixels(self) -> "PaintInput":
        if sum(run.length for run in self.patch.runs) > 256:
            raise ValueError("Pixel Patch exceeds the 256-pixel Operation Limit")
        return self


class CreateStep(PublicModel):
    operation: Literal["sprite create"]
    input: CreateInput


class GetStep(PublicModel):
    operation: Literal["sprite get"]
    input: GetInput


class PaintStep(PublicModel):
    operation: Literal["paint apply"]
    input: PaintInput


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
        create_indexes = [
            index
            for index, step in enumerate(self.steps)
            if step.operation == "sprite create"
        ]
        if create_indexes and create_indexes != [0]:
            raise ValueError("Sprite creation is allowed only as the first Plan Step")
        creates = bool(create_indexes)
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
            same_file = (
                Path(self.source_sprite_file).expanduser().absolute()
                == Path(self.target_sprite_file).expanduser().absolute()
            )
            if same_file != self.in_place:
                raise ValueError("Source/Target equality must match in_place intent")
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


def check_plan(
    request: PlanCheckRequest, _services: OperationServices
) -> PlanCheckResult:
    return PlanCheckResult(
        step_count=len(request.plan.steps), commit_required=request.plan.commit_required
    )


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
)
