"""Frame-based Palette Changes, exact Entry edits, and native capability gaps."""

from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.document.sprite import (
    SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    PaletteEntry,
)
from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    validate_native_sprite_path,
)
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
    CapabilityGap,
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
PALETTE_SET_HANDLER = PackagedHandler(
    "palette_set",
    "color/palette_set.lua",
    (
        *PALETTE_READ_HANDLER.support_resources,
        SPRITE_PERSISTENCE_RESOURCE,
        DIGEST_RESOURCE,
    ),
)
PALETTE_READ_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection"],
)
PALETTE_SET_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_palette_entries"],
)
PALETTE_PROBE_RESOURCES = (PALETTE_SUPPORT_RESOURCE, SPRITE_PERSISTENCE_RESOURCE)


def palette_lifecycle_gaps(aseprite_version: str) -> list[CapabilityGap]:
    """Report bounded native lifecycle evidence without registering unsupported commands."""
    if aseprite_version.partition("-")[0] != "1.3.18.5":
        return []
    return [
        CapabilityGap(
            capability=f"spa palette {operation}",
            aseprite_version=aseprite_version,
            evidence=(
                "Aseprite 1.3.18.5 has no public non-interactive Lua seam to add/remove "
                "Palette Changes: Palette.frame/frameNumber are read-only and Sprite has "
                "no newPalette/deletePalette. Entry edits target existing changes. "
                "A later public seam needs a successful save/close/reopen probe before admission."
            ),
        )
        for operation in ("add", "remove")
    ]


class PaletteListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)

    _validate_sprite = field_validator("sprite_file")(validate_native_sprite_path)


class PaletteGetRequest(PaletteListRequest):
    frame_number: int = Field(ge=1)


class PaletteSetRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    palette_frame_number: int = Field(ge=1)
    entries: list[PaletteEntry] = Field(min_length=1)

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_intent(self) -> "PaletteSetRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        indexes = [entry.index for entry in self.entries]
        if len(set(indexes)) != len(indexes):
            raise ValueError("Each Palette Index can occur only once in an Entry edit")
        return self


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


class PaletteSetEvidence(PaletteTimeline):
    palette: PaletteChange
    persisted_reopen_verified: Literal[True]


class PaletteSetResult(PaletteSetEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa palette set"] = "spa palette set"
    target_commit: TargetCommit


class PaletteFrameDetails(PublicModel):
    kind: Literal["palette_frame"] = "palette_frame"
    frame_number: int = Field(ge=1)
    frame_count: int = Field(ge=1)


class PaletteChangeDetails(PublicModel):
    kind: Literal["palette_change"] = "palette_change"
    palette_frame_number: int = Field(ge=1)
    frame_count: int = Field(ge=1)


class PaletteEntryDetails(PublicModel):
    kind: Literal["palette_entry"] = "palette_entry"
    palette_frame_number: int = Field(ge=1)
    index: int = Field(ge=0)
    palette_size: int = Field(ge=1)


PALETTE_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "palette_frame_out_of_bounds",
        "The requested Frame is outside the Sprite timeline",
        "input",
        PaletteFrameDetails,
    ),
    FailureCodeSpec(
        "palette_change_missing",
        "No Palette Change starts at the requested Frame",
        "input",
        PaletteChangeDetails,
    ),
    FailureCodeSpec(
        "palette_index_out_of_bounds",
        "An Entry edit addresses an index outside the Palette",
        "input",
        PaletteEntryDetails,
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
        # Palette addresses cross Lua JSON as decimal text. Keep even invalid large
        # addresses exact in the public Failure Envelope without a new input limit.
        wire_details = rejected["details"]
        if not isinstance(wire_details, dict):
            raise TypeError("Rejection details must be an object")
        details = spec.details_type.model_validate(
            {
                key: int(value)
                if key in {"frame_number", "palette_frame_number", "index"}
                and isinstance(value, str)
                else value
                for key, value in wire_details.items()
            }
        )
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
        payload["frame_number"] = str(request.frame_number)
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


def set_palette(
    request: PaletteSetRequest, services: OperationServices
) -> PaletteSetResult:
    completion = prepare_mutation(
        services.target_files,
        Path(request.source_sprite_file),
        Path(request.target_sprite_file),
        in_place=request.in_place,
        overwrite=request.overwrite,
        identity_change_message="Source/Target publication identity changed before Target Commit",
    )
    observation = services.probe_runtime(request)
    with completion as mutation:
        invocation = services.invoke_kernel(
            observation,
            PALETTE_SET_HANDLER,
            {
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(mutation.staged_sprite_file),
                "palette_frame_number": str(request.palette_frame_number),
                "entries": [
                    {"index": str(entry.index), "color": entry.color.model_dump()}
                    for entry in request.entries
                ],
            },
            request.timeout_seconds,
        )
        _reject(invocation)
        try:
            evidence = PaletteSetEvidence.model_validate(invocation.payload)
            selected = next(
                change
                for change in evidence.palette_changes
                if change.palette_frame_number == request.palette_frame_number
            )
            if selected != evidence.palette or any(
                edit.index >= len(selected.entries)
                or selected.entries[edit.index] != edit
                for edit in request.entries
            ):
                raise ValueError(
                    "Persisted Palette does not contain the requested Entry edits"
                )
        except (ValueError, StopIteration) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Invalid persisted Palette evidence",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        committed = mutation.commit()
        return PaletteSetResult(**evidence.model_dump(), target_commit=committed)


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
    OperationDescriptor(
        "palette set",
        PaletteSetRequest,
        PaletteSetResult,
        set_palette,
        lambda result: result.target_commit.target_sprite_file,
        PALETTE_SET_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "palette_change_missing",
            "palette_index_out_of_bounds",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
