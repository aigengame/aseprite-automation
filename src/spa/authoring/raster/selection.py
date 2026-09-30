"""Explicit Selection authoring and verification in Raster Authoring."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, JsonValue, TypeAdapter, ValidationError, model_validator

from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    ArtifactVerificationEvidence,
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import (
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.contracts.raster import (
    SELECTION_MASK_RESOURCE,
    AllSelection,
    EmptySelection,
    MaskSelection,
    Point,
    PositiveRectangle,
    SelectionApplication,
)
from spa.delivery.export import ExportDestination


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


class SelectionMorphologyRequest(SelectionCanvasRequest):
    radius: int = Field(ge=1)
    shape: Literal["circle", "square"]


class SelectionTranslation(PublicModel):
    kind: Literal["translate"]
    offset: Point


class SelectionFlip(PublicModel):
    kind: Literal["flip"]
    axis: Literal["horizontal", "vertical"]


class SelectionRotation(PublicModel):
    kind: Literal["rotate"]
    angle: Literal[90, -90, 180]


class SelectionScale(PublicModel):
    kind: Literal["scale"]
    width: int = Field(ge=1)
    height: int = Field(ge=1)


SelectionTransform = Annotated[
    SelectionTranslation | SelectionFlip | SelectionRotation | SelectionScale,
    Field(discriminator="kind"),
]


class SelectionTransformRequest(SelectionCanvasRequest):
    transform: SelectionTransform


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


class MorphologyFacts(SelectionFacts):
    canvas: PositiveRectangle
    radius: int = Field(ge=1)
    shape: Literal["circle", "square"]


class SelectionGrowResult(MorphologyFacts):
    status: Literal["success"] = "success"
    operation: Literal["spa selection grow"] = "spa selection grow"


class SelectionShrinkResult(MorphologyFacts):
    status: Literal["success"] = "success"
    operation: Literal["spa selection shrink"] = "spa selection shrink"


class SelectionTransformResult(SelectionFacts):
    status: Literal["success"] = "success"
    operation: Literal["spa selection transform"] = "spa selection transform"
    canvas: PositiveRectangle
    source_bounds: PositiveRectangle | None = None
    target_placement: PositiveRectangle | None = None


class SelectionValidateRequest(RuntimeRequest):
    coordinate_space: str
    selection: JsonValue = Field(
        description="Canonical Selection or Artifact reference to validate; invalid encoding produces Findings."
    )
    canvas: PositiveRectangle | None = None


class SelectionCheck(PublicModel):
    check: Literal["encoding", "coordinate_space", "containment"]
    matches: bool


class SelectionFinding(PublicModel):
    kind: Literal[
        "selection_encoding_invalid",
        "selection_coordinate_space_invalid",
        "selection_out_of_bounds",
    ]
    subject: Literal["selection"] = "selection"
    message: str


class SelectionValidateResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa selection validate"] = "spa selection validate"
    valid: bool
    checks: list[SelectionCheck]
    findings: list[SelectionFinding]


class SelectionDestination(PublicModel):
    path: str = Field(
        min_length=6,
        pattern=r"^[^\x00\r\n]+\.json$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    if_exists: Literal["fail", "replace"]


class SelectionExportRequest(SelectionRequest):
    selection: SelectionInput
    destination: SelectionDestination


class SelectionPreviewRequest(SelectionCanvasRequest):
    destination: ExportDestination


class SelectionArtifact(PublicModel):
    role: Literal["selection-mask"] = "selection-mask"
    media_type: Literal["application/json"] = "application/json"
    format: Literal["json"] = "json"
    path: str
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SelectionPreviewArtifact(PublicModel):
    role: Literal["selection-preview"] = "selection-preview"
    media_type: Literal["image/png"] = "image/png"
    format: Literal["png"] = "png"
    path: str
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SelectionExportResult(SelectionFacts):
    status: Literal["success"] = "success"
    operation: Literal["spa selection export"] = "spa selection export"
    artifact: SelectionArtifact


class SelectionPreviewResult(SelectionFacts):
    status: Literal["success"] = "success"
    operation: Literal["spa selection preview"] = "spa selection preview"
    canvas: PositiveRectangle
    artifact: SelectionPreviewArtifact


SELECTION_SUPPORT_RESOURCE = PackagedResource(
    "selection_support", "raster/selection/selection_support.lua"
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
        PackagedHandler(
            name,
            f"raster/selection/{name}.lua",
            (SELECTION_MASK_RESOURCE, SELECTION_SUPPORT_RESOURCE),
        ),
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


def _canvas_payload(
    request: SelectionCanvasRequest, services: OperationServices
) -> dict:
    payload = request.model_dump(mode="json", exclude={"aseprite", "timeout_seconds"})
    payload["selection"] = _load(request.selection, services).model_dump(mode="json")
    return payload


def grow_selection(
    request: SelectionMorphologyRequest, services: OperationServices
) -> SelectionGrowResult:
    invocation = _invoke(
        request, services, "selection_grow", _canvas_payload(request, services)
    )
    return _result(invocation, SelectionGrowResult)


def shrink_selection(
    request: SelectionMorphologyRequest, services: OperationServices
) -> SelectionShrinkResult:
    invocation = _invoke(
        request, services, "selection_shrink", _canvas_payload(request, services)
    )
    return _result(invocation, SelectionShrinkResult)


def transform_selection(
    request: SelectionTransformRequest, services: OperationServices
) -> SelectionTransformResult:
    invocation = _invoke(
        request, services, "selection_transform", _canvas_payload(request, services)
    )
    return _result(invocation, SelectionTransformResult)


def validate_selection(
    request: SelectionValidateRequest, services: OperationServices
) -> SelectionValidateResult:
    findings: list[SelectionFinding] = []
    space_matches = request.coordinate_space == "canvas-pixel"
    checks = [SelectionCheck(check="coordinate_space", matches=space_matches)]
    if not space_matches:
        findings.append(
            SelectionFinding(
                kind="selection_coordinate_space_invalid",
                message="Selection uses Canvas Pixel coordinates",
            )
        )
    value = None
    try:
        parsed = TypeAdapter(SelectionInput).validate_python(request.selection)
        value = _load(parsed, services)
    except ValidationError as exc:
        findings.append(
            SelectionFinding(kind="selection_encoding_invalid", message=str(exc))
        )
    except OperationIssue as exc:
        if exc.code != "selection_invalid":
            raise
        findings.append(
            SelectionFinding(kind="selection_encoding_invalid", message=str(exc))
        )
    checks.append(SelectionCheck(check="encoding", matches=value is not None))
    if value is not None and space_matches:
        # The native Mask establishes actual membership after wire validation.
        payload = {"shape": {"kind": "mask", "input": value.model_dump(mode="json")}}
        facts = _result(
            _invoke(request, services, "selection_create", payload), SelectionFacts
        )
        if request.canvas is not None:
            b, c = facts.bounds, request.canvas
            contained = b is None or (
                b.x >= c.x
                and b.y >= c.y
                and b.x + b.width <= c.x + c.width
                and b.y + b.height <= c.y + c.height
            )
            checks.append(SelectionCheck(check="containment", matches=contained))
            if not contained:
                findings.append(
                    SelectionFinding(
                        kind="selection_out_of_bounds",
                        message="Selected coverage is outside the declared Canvas Rectangle",
                    )
                )
    return SelectionValidateResult(valid=not findings, checks=checks, findings=findings)


def _verification_failed(
    invocation: KernelInvocationResult, staged: Path, message: str
) -> RuntimeIssue:
    return RuntimeIssue(
        "artifact_verification_failed",
        message,
        ArtifactVerificationEvidence(str(staged), message),
        invocation.diagnostics,
    )


def export_selection(
    request: SelectionExportRequest, services: OperationServices
) -> SelectionExportResult:
    files = services.artifact_files
    assert files is not None
    value = _load(request.selection, services)
    destination = files.normalize_destination(request.destination.path)
    if isinstance(request.selection, SelectionArtifactInput):
        files.ensure_source_separate(Path(request.selection.path), destination)
    staged = files.staged_path(destination, if_exists=request.destination.if_exists)
    try:
        invocation = _invoke(
            request,
            services,
            "selection_export",
            {"selection": value.model_dump(mode="json"), "staged_file": str(staged)},
        )
        facts = _result(invocation, SelectionFacts)
        artifact = files.read_staged(staged)
        try:
            decoded = SELECTION_VALUE.validate_json(artifact.payload)
        except ValidationError as exc:
            raise _verification_failed(
                invocation, staged, "Exported JSON is not a canonical Selection"
            ) from exc
        if decoded != facts.selection:
            raise _verification_failed(
                invocation,
                staged,
                "Exported JSON differs from native Selection evidence",
            )
        if isinstance(request.selection, SelectionArtifactInput):
            files.ensure_source_separate(Path(request.selection.path), destination)
        published = files.publish(
            staged,
            destination,
            if_exists=request.destination.if_exists,
            sha256=artifact.sha256,
        )
        return SelectionExportResult(
            **facts.model_dump(),
            artifact=SelectionArtifact(
                path=published.path,
                byte_size=published.byte_size,
                sha256=published.sha256,
            ),
        )
    finally:
        files.discard(staged)


def preview_selection(
    request: SelectionPreviewRequest, services: OperationServices
) -> SelectionPreviewResult:
    files, verify_png = services.artifact_files, services.verify_png
    assert files is not None and verify_png is not None
    value = _load(request.selection, services)
    destination = files.normalize_destination(request.destination.path)
    if isinstance(request.selection, SelectionArtifactInput):
        files.ensure_source_separate(Path(request.selection.path), destination)
    staged = files.staged_path(destination, if_exists=request.destination.if_exists)
    rendered = files.rendered_path(staged)
    try:
        invocation = _invoke(
            request,
            services,
            "selection_preview",
            {
                "selection": value.model_dump(mode="json"),
                "canvas": request.canvas.model_dump(),
                "staged_file": str(staged),
                "rendered_file": str(rendered),
            },
        )
        facts = _result(invocation, SelectionFacts)
        artifact = files.read_staged(staged)
        decoded = verify_png(artifact.payload, staged)
        native_bytes = files.read_staged(rendered).payload
        c = request.canvas
        if (
            decoded.width != c.width
            or decoded.height != c.height
            or len(native_bytes) != c.width * c.height * 4
            or decoded.rgba_bytes != native_bytes
        ):
            raise _verification_failed(
                invocation, staged, "Preview PNG differs from native binary coverage"
            )
        if isinstance(request.selection, SelectionArtifactInput):
            files.ensure_source_separate(Path(request.selection.path), destination)
        published = files.publish(
            staged,
            destination,
            if_exists=request.destination.if_exists,
            sha256=artifact.sha256,
        )
        return SelectionPreviewResult(
            **facts.model_dump(),
            canvas=request.canvas,
            artifact=SelectionPreviewArtifact(
                path=published.path,
                byte_size=published.byte_size,
                sha256=published.sha256,
            ),
        )
    finally:
        files.discard(staged)
        files.discard(rendered)


SELECTION_ARTIFACT_FAILURE_CODES = (
    *SELECTION_FAILURE_CODES,
    "artifact_verification_failed",
)

SELECTION_OPERATIONS = (
    OperationDescriptor(
        "selection create",
        SelectionCreateRequest,
        SelectionCreateResult,
        create_selection,
        lambda r: f"{r.pixel_count} selected pixels",
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
    OperationDescriptor(
        "selection grow",
        SelectionMorphologyRequest,
        SelectionGrowResult,
        grow_selection,
        lambda r: f"{r.pixel_count} selected pixels",
        SELECTION_REQUIREMENTS,
        SELECTION_FAILURE_CODES,
    ),
    OperationDescriptor(
        "selection shrink",
        SelectionMorphologyRequest,
        SelectionShrinkResult,
        shrink_selection,
        lambda r: f"{r.pixel_count} selected pixels",
        SELECTION_REQUIREMENTS,
        SELECTION_FAILURE_CODES,
    ),
    OperationDescriptor(
        "selection transform",
        SelectionTransformRequest,
        SelectionTransformResult,
        transform_selection,
        lambda r: f"{r.pixel_count} selected pixels",
        SELECTION_REQUIREMENTS,
        SELECTION_FAILURE_CODES,
    ),
    OperationDescriptor(
        "selection validate",
        SelectionValidateRequest,
        SelectionValidateResult,
        validate_selection,
        lambda r: "valid Selection" if r.valid else f"{len(r.findings)} Findings",
        SELECTION_REQUIREMENTS,
        SELECTION_FAILURE_CODES,
    ),
    OperationDescriptor(
        "selection export",
        SelectionExportRequest,
        SelectionExportResult,
        export_selection,
        lambda r: r.artifact.path,
        SELECTION_REQUIREMENTS,
        SELECTION_ARTIFACT_FAILURE_CODES,
        execution_kind="export",
        side_effects=("publishes one verified Selection Artifact",),
    ),
    OperationDescriptor(
        "selection preview",
        SelectionPreviewRequest,
        SelectionPreviewResult,
        preview_selection,
        lambda r: r.artifact.path,
        SELECTION_REQUIREMENTS,
        SELECTION_ARTIFACT_FAILURE_CODES,
        execution_kind="export",
        side_effects=("publishes one verified Selection Artifact",),
    ),
)
