"""Frame authoring and inspection contracts over Aseprite's timeline."""

from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.contracts import (
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
    ValidationIssue,
)
from spa.mutation import TargetCommit, source_target_identity_issue
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.paint import DIGEST_RESOURCE
from spa.ports import (
    KernelInvocationResult,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PostconditionEvidence,
    RequestIssue,
    ResponseEvidence,
    RuntimeIssue,
    TargetCommitEvidence,
)
from spa.raster import ColorValue
from spa.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_GET_HANDLER,
    SPRITE_INSPECTION_RESOURCE,
    FrameFacts,
    SpriteGetRequest,
    SpriteInspection,
    _inspection_from_kernel,
    validated_scope,
)


def _native_sprite_path(value: str) -> str:
    if Path(value).suffix.lower() != ".aseprite":
        raise ValueError("Sprite file must use the .aseprite extension")
    return value


class FrameListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)

    _validate_sprite = field_validator("sprite_file")(_native_sprite_path)


class FrameGetRequest(FrameListRequest):
    frame_number: int = Field(ge=1, strict=True)


class FrameListResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa frame list"] = "spa frame list"
    sprite_file: str
    frames: list[FrameFacts]


class FrameGetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa frame get"] = "spa frame get"
    sprite_file: str
    frame: FrameFacts


class FrameAddInput(PublicModel):
    frame_number: int = Field(ge=1, strict=True)
    duration_ms: int = Field(ge=1, le=65535, strict=True)
    background_color: ColorValue | None = None


class FrameDuplicateInput(PublicModel):
    source_frame_number: int = Field(ge=1, strict=True)
    cel_mode: Literal["copy", "link"]
    duration_ms: int | None = Field(default=None, ge=1, le=65535, strict=True)


class _FrameMutationRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool

    _validate_source = field_validator("source_sprite_file")(_native_sprite_path)
    _validate_target = field_validator("target_sprite_file")(_native_sprite_path)

    @model_validator(mode="after")
    def validate_target_commit_intent(self) -> "_FrameMutationRequest":
        if self.in_place and not self.overwrite:
            raise ValueError("in_place requires overwrite permission")
        return self


class FrameAddRequest(_FrameMutationRequest, FrameAddInput):
    pass


class FrameDuplicateRequest(_FrameMutationRequest, FrameDuplicateInput):
    pass


class TagRangeAdjustment(PublicModel):
    tag_number: int = Field(ge=1)
    name: str
    before_from_frame: int = Field(ge=1)
    before_to_frame: int = Field(ge=1)
    after_from_frame: int = Field(ge=1)
    after_to_frame: int = Field(ge=1)


class FrameMutationEvidence(PublicModel):
    inserted_frame: FrameFacts
    tag_adjustments: list[TagRangeAdjustment]
    source_cel_count: int = Field(ge=0)
    inserted_cel_count: int = Field(ge=0)
    cel_relationships_verified: Literal[True]
    persisted_reopen_verified: bool


class FrameAddResult(FrameMutationEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa frame add"] = "spa frame add"
    persisted_reopen_verified: Literal[True]
    sprite: SpriteInspection
    target_commit: TargetCommit


class FrameDuplicateResult(FrameMutationEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa frame duplicate"] = "spa frame duplicate"
    persisted_reopen_verified: Literal[True]
    sprite: SpriteInspection
    target_commit: TargetCommit


FRAME_READ_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection"],
)
FRAME_MUTATION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_frame_authoring"],
)
FRAME_SUPPORT_RESOURCE = PackagedResource("frame", "frame_support.lua")
FRAME_MUTATE_HANDLER = PackagedHandler(
    "frame_mutate",
    (SPRITE_INSPECTION_RESOURCE, FRAME_SUPPORT_RESOURCE, DIGEST_RESOURCE),
)


def _read_frames(
    request: FrameListRequest, services: OperationServices
) -> list[FrameFacts]:
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        SPRITE_GET_HANDLER,
        {"sprite_file": request.sprite_file, "inspection_scope": ["frames"]},
        request.timeout_seconds,
    )
    sprite = _inspection_from_kernel(invocation)
    frames = sprite.frames
    if (
        frames is None
        or len(frames) != sprite.metadata.frame_count
        or any(frame.frame_number != index for index, frame in enumerate(frames, 1))
    ):
        raise RuntimeIssue(
            "postcondition_failed",
            "Frame inspection is incomplete",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="Frame count differs from inspection metadata",
            ),
            invocation.diagnostics,
        )
    return frames


def list_frames(
    request: FrameListRequest, services: OperationServices
) -> FrameListResult:
    return FrameListResult(
        sprite_file=request.sprite_file, frames=_read_frames(request, services)
    )


def get_frame(request: FrameGetRequest, services: OperationServices) -> FrameGetResult:
    frames = _read_frames(request, services)
    if request.frame_number > len(frames):
        raise RequestIssue(
            [
                ValidationIssue(
                    location=["frame_number"],
                    code="frame_not_found",
                    message="Frame Number is outside the Sprite timeline",
                )
            ]
        )
    return FrameGetResult(
        sprite_file=request.sprite_file, frame=frames[request.frame_number - 1]
    )


def validate_frame_evidence(
    input: FrameAddInput | FrameDuplicateInput,
    evidence: FrameMutationEvidence,
    invocation: KernelInvocationResult,
) -> None:
    expected_number = (
        input.frame_number
        if isinstance(input, FrameAddInput)
        else input.source_frame_number + 1
    )
    expected_duration = input.duration_ms
    if (
        evidence.inserted_frame.frame_number != expected_number
        or (
            expected_duration is not None
            and evidence.inserted_frame.duration_ms != expected_duration
        )
        or (isinstance(input, FrameAddInput) and evidence.source_cel_count != 0)
        or (isinstance(input, FrameAddInput) and evidence.inserted_cel_count > 1)
        or (
            isinstance(input, FrameDuplicateInput)
            and evidence.source_cel_count != evidence.inserted_cel_count
        )
    ):
        raise RuntimeIssue(
            "postcondition_failed",
            "Persisted Frame evidence differs from the request",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="inserted Frame or Cel facts disagree",
            ),
            invocation.diagnostics,
        )


def _mutate(
    request: FrameAddRequest | FrameDuplicateRequest,
    services: OperationServices,
    operation: Literal["add", "duplicate"],
) -> FrameAddResult | FrameDuplicateResult:
    target = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files,
        Path(request.source_sprite_file),
        target,
        request.in_place,
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    observation = services.probe_runtime(request)
    staged = services.target_files.staged_path(target)
    input_fields = (
        FrameAddInput.model_fields
        if operation == "add"
        else FrameDuplicateInput.model_fields
    )
    payload = {
        "operation": operation,
        "source_sprite_file": request.source_sprite_file,
        "staged_sprite_file": str(staged),
        "input": request.model_dump(mode="json", include=set(input_fields)),
    }
    try:
        invocation = services.invoke_kernel(
            observation, FRAME_MUTATE_HANDLER, payload, request.timeout_seconds
        )
        try:
            evidence = FrameMutationEvidence.model_validate(
                {
                    key: value
                    for key, value in invocation.payload.items()
                    if key != "sprite"
                }
            )
            sprite = SpriteInspection.model_validate(invocation.payload["sprite"])
        except (KeyError, TypeError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Packaged Frame handler returned invalid mutation evidence",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        validate_frame_evidence(request, evidence, invocation)
        if not evidence.persisted_reopen_verified:
            raise RuntimeIssue(
                "postcondition_failed",
                "Frame mutation lacks persisted Sprite evidence",
                PostconditionEvidence(
                    response_path=invocation.response_path,
                    reason="persisted Sprite verification is absent",
                ),
                invocation.diagnostics,
            )
        validated_scope(
            SpriteGetRequest(
                sprite_file=request.target_sprite_file,
                inspection_scope=list(INSPECTION_SECTIONS),
            ),
            sprite,
            invocation,
        )
        frames = sprite.frames
        cels = sprite.cels
        tags = sprite.tags
        number = evidence.inserted_frame.frame_number
        if (
            frames is None
            or cels is None
            or tags is None
            or number > len(frames)
            or frames[number - 1] != evidence.inserted_frame
            or sum(cel.frame_number == number for cel in cels)
            != evidence.inserted_cel_count
            or any(
                adjustment.tag_number > len(tags)
                or tags[adjustment.tag_number - 1].name != adjustment.name
                or tags[adjustment.tag_number - 1].from_frame
                != adjustment.after_from_frame
                or tags[adjustment.tag_number - 1].to_frame != adjustment.after_to_frame
                for adjustment in evidence.tag_adjustments
            )
        ):
            raise RuntimeIssue(
                "postcondition_failed",
                "Persisted Sprite differs from Frame mutation evidence",
                PostconditionEvidence(
                    response_path=invocation.response_path,
                    reason="Frame, Cel, or Tag facts disagree",
                ),
                invocation.diagnostics,
            )
        identity_issue = source_target_identity_issue(
            services.target_files,
            Path(request.source_sprite_file),
            target,
            request.in_place,
        )
        if identity_issue is not None:
            raise RuntimeIssue(
                "target_commit_failed",
                "Source/Target publication identity changed before Target Commit",
                TargetCommitEvidence(str(target), "source_target_identity_changed"),
            )
        committed = services.target_files.commit(
            staged, target, overwrite=request.overwrite
        )
        result = {
            **evidence.model_dump(),
            "sprite": sprite,
            "target_commit": TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
        }
        if operation == "add":
            return FrameAddResult.model_validate(result)
        return FrameDuplicateResult.model_validate(result)
    finally:
        services.target_files.discard(staged)


def add_frame(request: FrameAddRequest, services: OperationServices) -> FrameAddResult:
    result = _mutate(request, services, "add")
    assert isinstance(result, FrameAddResult)
    return result


def duplicate_frame(
    request: FrameDuplicateRequest, services: OperationServices
) -> FrameDuplicateResult:
    result = _mutate(request, services, "duplicate")
    assert isinstance(result, FrameDuplicateResult)
    return result


FRAME_OPERATIONS = (
    OperationDescriptor(
        "frame list",
        FrameListRequest,
        FrameListResult,
        list_frames,
        lambda result: f"{len(result.frames)} Frames",
        FRAME_READ_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
        plan_eligible=True,
    ),
    OperationDescriptor(
        "frame get",
        FrameGetRequest,
        FrameGetResult,
        get_frame,
        lambda result: (
            f"Frame {result.frame.frame_number}: {result.frame.duration_ms} ms"
        ),
        FRAME_READ_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
        plan_eligible=True,
    ),
    OperationDescriptor(
        "frame add",
        FrameAddRequest,
        FrameAddResult,
        add_frame,
        lambda result: result.target_commit.target_sprite_file,
        FRAME_MUTATION_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        plan_eligible=True,
        probe_before_execute=False,
    ),
    OperationDescriptor(
        "frame duplicate",
        FrameDuplicateRequest,
        FrameDuplicateResult,
        duplicate_frame,
        lambda result: result.target_commit.target_sprite_file,
        FRAME_MUTATION_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        plan_eligible=True,
        probe_before_execute=False,
    ),
)
