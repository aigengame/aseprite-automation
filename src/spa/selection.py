"""Explicit Selection authoring and verification in Raster Authoring."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, ValidationError, model_validator

from spa.contracts import (
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.ports import (
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.raster import (
    AllSelection,
    EmptySelection,
    MaskSelection,
    PositiveRectangle,
    SelectionApplication,
)


class SelectionArtifactInput(PublicModel):
    kind: Literal["artifact"]
    path: str = Field(min_length=1)


SelectionInput = Annotated[
    EmptySelection | AllSelection | MaskSelection | SelectionArtifactInput,
    Field(discriminator="kind"),
]
SELECTION_VALUE = TypeAdapter(SelectionApplication)


class SelectionDetails(PublicModel):
    kind: Literal["selection"] = "selection"
    reason: str


SELECTION_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "selection_invalid",
        "Artifact is not a canonical Selection value",
        "input",
        SelectionDetails,
    ),
    FailureCodeSpec(
        "selection_out_of_bounds",
        "Selection coverage is outside the declared Canvas Rectangle",
        "input",
        SelectionDetails,
    ),
)


class RectangleSelection(PublicModel):
    kind: Literal["rectangle"]
    rectangle: PositiveRectangle


class EllipseSelection(PublicModel):
    kind: Literal["ellipse"]
    bounds: PositiveRectangle


class MaskConstruction(PublicModel):
    kind: Literal["mask"]
    input: SelectionInput


class SelectionRequest(RuntimeRequest):
    coordinate_space: Literal["canvas-pixel"]


class SelectionCreateRequest(SelectionRequest):
    shape: Annotated[
        RectangleSelection | EllipseSelection | MaskConstruction,
        Field(discriminator="kind"),
    ]


class SelectionCombineRequest(SelectionRequest):
    left: SelectionInput
    right: SelectionInput
    mode: Literal["union", "intersect", "subtract", "xor"]


class SelectionCanvasRequest(SelectionRequest):
    selection: SelectionInput
    canvas: PositiveRectangle


class SelectionFacts(PublicModel):
    coordinate_space: Literal["canvas-pixel"]
    selection: SelectionApplication
    bounds: PositiveRectangle | None = None
    pixel_count: int = Field(ge=0)

    @model_validator(mode="after")
    def coherent_coverage_facts(self) -> "SelectionFacts":
        value = self.selection
        bounds = None
        count = 0
        if isinstance(value, AllSelection):
            bounds = value.rectangle
            count = bounds.width * bounds.height
        elif isinstance(value, MaskSelection):
            bounds = value.bounds
            count = sum(run.length for row in value.rows for run in row.runs)
        if self.bounds != bounds or self.pixel_count != count:
            raise ValueError(
                "Selection bounds or pixel count differs from canonical coverage"
            )
        return self


class SelectionCreateResult(SelectionFacts):
    status: Literal["success"] = "success"
    operation: Literal["spa selection create"] = "spa selection create"


class SelectionCombineResult(SelectionFacts):
    status: Literal["success"] = "success"
    operation: Literal["spa selection combine"] = "spa selection combine"


class SelectionInvertResult(SelectionFacts):
    status: Literal["success"] = "success"
    operation: Literal["spa selection invert"] = "spa selection invert"
    canvas: PositiveRectangle


SELECTION_MASK_RESOURCE = PackagedResource("selection_mask", "selection_mask.lua")
SELECTION_SUPPORT_RESOURCE = PackagedResource(
    "selection_support", "selection_support.lua"
)
SELECTION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_selection"],
)


def _load(value: SelectionInput, services: OperationServices) -> SelectionApplication:
    if not isinstance(value, SelectionArtifactInput):
        return value
    files = services.artifact_files
    assert files is not None
    raw = files.read_input(Path(value.path))
    try:
        return SELECTION_VALUE.validate_json(raw)
    except ValidationError as exc:
        raise OperationIssue(
            "selection_invalid",
            "Artifact is not a canonical Selection",
            SelectionDetails(reason=str(exc)),
        ) from exc


def _invoke(
    request: RuntimeRequest, services: OperationServices, name: str, payload: dict
):
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        PackagedHandler(name, (SELECTION_MASK_RESOURCE, SELECTION_SUPPORT_RESOURCE)),
        payload,
        request.timeout_seconds,
    )
    rejection = invocation.payload.get("rejection")
    if (
        isinstance(rejection, dict)
        and isinstance(rejection.get("code"), str)
        and rejection["code"] in {spec.code for spec in SELECTION_FAILURE_CODE_SPECS}
        and isinstance(rejection.get("message"), str)
    ):
        raise OperationIssue(
            rejection["code"],
            rejection["message"],
            SelectionDetails(reason=rejection["message"]),
        )
    return invocation


def _result[T: PublicModel](invocation: KernelInvocationResult, model: type[T]) -> T:
    try:
        return model.model_validate(invocation.payload)
    except ValidationError as exc:
        raise RuntimeIssue(
            "response_malformed",
            f"Invalid Selection evidence: {exc}",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc


def create_selection(
    request: SelectionCreateRequest, services: OperationServices
) -> SelectionCreateResult:
    shape = request.shape.model_dump(mode="json")
    if isinstance(request.shape, MaskConstruction):
        shape["input"] = _load(request.shape.input, services).model_dump(mode="json")
    invocation = _invoke(request, services, "selection_create", {"shape": shape})
    return _result(invocation, SelectionCreateResult)


def combine_selection(
    request: SelectionCombineRequest, services: OperationServices
) -> SelectionCombineResult:
    invocation = _invoke(
        request,
        services,
        "selection_combine",
        {
            "left": _load(request.left, services).model_dump(mode="json"),
            "right": _load(request.right, services).model_dump(mode="json"),
            "mode": request.mode,
        },
    )
    return _result(invocation, SelectionCombineResult)


def invert_selection(
    request: SelectionCanvasRequest, services: OperationServices
) -> SelectionInvertResult:
    invocation = _invoke(
        request,
        services,
        "selection_invert",
        {
            "selection": _load(request.selection, services).model_dump(mode="json"),
            "canvas": request.canvas.model_dump(mode="json"),
        },
    )
    return _result(invocation, SelectionInvertResult)


SELECTION_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    "artifact_file_failed",
    *(spec.code for spec in SELECTION_FAILURE_CODE_SPECS),
)


SELECTION_OPERATIONS = (
    OperationDescriptor(
        "selection create",
        SelectionCreateRequest,
        SelectionCreateResult,
        create_selection,
        lambda result: f"{result.pixel_count} selected pixels",
        SELECTION_REQUIREMENTS,
        SELECTION_FAILURE_CODES,
    ),
    OperationDescriptor(
        "selection combine",
        SelectionCombineRequest,
        SelectionCombineResult,
        combine_selection,
        lambda r: f"{r.pixel_count} selected pixels",
        SELECTION_REQUIREMENTS,
        SELECTION_FAILURE_CODES,
    ),
    OperationDescriptor(
        "selection invert",
        SelectionCanvasRequest,
        SelectionInvertResult,
        invert_selection,
        lambda r: f"{r.pixel_count} selected pixels",
        SELECTION_REQUIREMENTS,
        SELECTION_FAILURE_CODES,
    ),
)
