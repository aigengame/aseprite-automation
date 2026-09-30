"""Frame-based Palette Changes and their public read operations."""

from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.authoring.document.sprite import (
    SPRITE_INSPECTION_RESOURCES,
    PaletteEntry,
)
from spa.contracts.mutation import validate_native_sprite_path
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
from spa.contracts.public import (
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)

EFFECTIVE_PALETTE_RESOURCE = PackagedResource(
    "effective_palette", "color/effective_palette.lua"
)
PALETTE_SUPPORT_RESOURCE = PackagedResource("palette", "color/palette_support.lua")
PALETTE_READ_HANDLER = PackagedHandler(
    "palette_read",
    "color/palette_read.lua",
    (
        *SPRITE_INSPECTION_RESOURCES,
        EFFECTIVE_PALETTE_RESOURCE,
        PALETTE_SUPPORT_RESOURCE,
    ),
)
PALETTE_READ_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection"],
)


class PaletteListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)

    _validate_sprite = field_validator("sprite_file")(validate_native_sprite_path)


class PaletteGetRequest(PaletteListRequest):
    frame_number: int = Field(ge=1)


class PaletteFrameRange(PublicModel):
    from_frame: int = Field(ge=1)
    to_frame: int = Field(ge=1)


class PaletteChange(PublicModel):
    palette_frame_number: int = Field(ge=1)
    effective_frame_range: PaletteFrameRange
    entries: list[PaletteEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_change(self) -> "PaletteChange":
        area = self.effective_frame_range
        if (
            area.from_frame != self.palette_frame_number
            or area.to_frame < area.from_frame
        ):
            raise ValueError("Effective Frame Range must start at the Palette Change")
        if [entry.index for entry in self.entries] != list(range(len(self.entries))):
            raise ValueError(
                "Palette Entries must be complete and ordered from index zero"
            )
        return self


class PaletteTimeline(PublicModel):
    frame_count: int = Field(ge=1)
    palette_changes: list[PaletteChange] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_timeline(self) -> "PaletteTimeline":
        next_frame = 1
        for change in self.palette_changes:
            if change.palette_frame_number != next_frame:
                raise ValueError("Palette Changes must cover the timeline in order")
            next_frame = change.effective_frame_range.to_frame + 1
        if next_frame != self.frame_count + 1:
            raise ValueError("Effective Palette coverage must end at the last Frame")
        return self


class PaletteListResult(PaletteTimeline):
    status: Literal["success"] = "success"
    operation: Literal["spa palette list"] = "spa palette list"


class PaletteGetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa palette get"] = "spa palette get"
    frame_number: int = Field(ge=1)
    palette: PaletteChange


class PaletteFrameDetails(PublicModel):
    kind: Literal["palette_frame"] = "palette_frame"
    frame_number: int = Field(ge=1)
    frame_count: int = Field(ge=1)


PALETTE_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "palette_frame_out_of_bounds",
        "The requested Frame is outside the Sprite timeline",
        "input",
        PaletteFrameDetails,
    ),
)


def _reject(invocation: KernelInvocationResult) -> None:
    rejected = invocation.payload.get("rejection")
    if rejected is None:
        return
    try:
        spec = next(
            spec for spec in PALETTE_FAILURE_CODE_SPECS if spec.code == rejected["code"]
        )
        details = spec.details_type.model_validate(rejected["details"])
        message = rejected["message"]
        if not isinstance(message, str):
            raise TypeError("Rejection message must be text")
    except (KeyError, TypeError, ValueError, StopIteration) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Invalid Palette rejection",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc
    raise OperationIssue(spec.code, message, details)


def _read(
    request: PaletteListRequest, services: OperationServices
) -> KernelInvocationResult:
    observation = services.probe_runtime(request)
    payload: dict[str, object] = {"sprite_file": request.sprite_file}
    if isinstance(request, PaletteGetRequest):
        payload["frame_number"] = request.frame_number
    invocation = services.invoke_kernel(
        observation, PALETTE_READ_HANDLER, payload, request.timeout_seconds
    )
    _reject(invocation)
    return invocation


def list_palettes(
    request: PaletteListRequest, services: OperationServices
) -> PaletteListResult:
    invocation = _read(request, services)
    try:
        return PaletteListResult.model_validate(invocation.payload)
    except ValidationError as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Invalid Palette timeline",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc


def get_palette(
    request: PaletteGetRequest, services: OperationServices
) -> PaletteGetResult:
    invocation = _read(request, services)
    try:
        result = PaletteGetResult.model_validate(invocation.payload)
        area = result.palette.effective_frame_range
        if (
            result.frame_number != request.frame_number
            or not area.from_frame <= result.frame_number <= area.to_frame
        ):
            raise ValueError("Effective Palette does not cover the requested Frame")
        return result
    except ValueError as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Invalid Effective Palette",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc


PALETTE_OPERATIONS = (
    OperationDescriptor(
        "palette list",
        PaletteListRequest,
        PaletteListResult,
        list_palettes,
        lambda result: f"{len(result.palette_changes)} Palette Changes",
        PALETTE_READ_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
    OperationDescriptor(
        "palette get",
        PaletteGetRequest,
        PaletteGetResult,
        get_palette,
        lambda result: (
            f"Frame {result.frame_number}: Palette Change {result.palette.palette_frame_number}"
        ),
        PALETTE_READ_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "palette_frame_out_of_bounds"),
    ),
)
