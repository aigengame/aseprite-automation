"""Frame authoring and inspection contracts over Aseprite's timeline."""

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.document.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_GET_HANDLER,
    SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    FrameFacts,
    SpriteGetRequest,
    SpriteInspection,
    _inspection_from_kernel,
    validated_scope,
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
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PostconditionEvidence,
    RequestIssue,
    ResponseEvidence,
    RuntimeIssue,
    TargetCommitEvidence,
)
from spa.contracts.public import (
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
    ValidationIssue,
)
from spa.contracts.raster import ColorValue


class FrameListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)

    _validate_sprite = field_validator("sprite_file")(validate_native_sprite_path)


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


class FrameMutationRequest(RuntimeRequest):
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
    def validate_target_commit_intent(self) -> "FrameMutationRequest":
        if self.in_place and not self.overwrite:
            raise ValueError("in_place requires overwrite permission")
        return self


class FrameAddRequest(FrameMutationRequest, FrameAddInput):
    pass


class FrameDuplicateRequest(FrameMutationRequest, FrameDuplicateInput):
    pass


class FrameSetInput(PublicModel):
    frame_number: int = Field(ge=1, strict=True)
    duration_ms: int = Field(ge=1, le=65535, strict=True)


class FrameMoveInput(PublicModel):
    source_frame_number: int = Field(ge=1, strict=True)
    target_frame_number: int = Field(
        ge=1, strict=True, description="One-based final position of the moved Frame"
    )


class FrameRemoveInput(PublicModel):
    frame_number: int = Field(ge=1, strict=True)


class FrameSetRequest(FrameMutationRequest, FrameSetInput):
    pass


class FrameMoveRequest(FrameMutationRequest, FrameMoveInput):
    pass


class FrameRemoveRequest(FrameMutationRequest, FrameRemoveInput):
    pass


class TagRangeAdjustment(PublicModel):
    tag_number: int = Field(ge=1)
    name: str
    before_from_frame: int = Field(ge=1)
    before_to_frame: int = Field(ge=1)
    after_from_frame: int = Field(ge=1)
    after_to_frame: int = Field(ge=1)


class CelRelationship(PublicModel):
    layer_path: list[int] = Field(min_length=1)
    source_frame_number: int = Field(ge=1)
    kind: Literal["copy", "link"]


class FrameMutationEvidence(PublicModel):
    inserted_frame: FrameFacts
    tag_adjustments: list[TagRangeAdjustment]
    source_cel_count: int = Field(ge=0)
    inserted_cel_count: int = Field(ge=0)
    background_fill: ColorValue | None
    cel_relationships: list[CelRelationship]
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


class FrameNumberChange(PublicModel):
    before_frame_number: int = Field(ge=1)
    after_frame_number: int | None = Field(default=None, ge=1)


class FrameEditEvidence(PublicModel):
    # Full native inspections expose the observed Cel, Tag, Slice, and Palette
    # effects, including native changes outside the addressed Frame.
    before: SpriteInspection
    frame_number_changes: list[FrameNumberChange]
    cel_content_verified: Literal[True]
    persisted_reopen_verified: bool


class FrameSetResult(FrameEditEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa frame set"] = "spa frame set"
    persisted_reopen_verified: Literal[True]
    sprite: SpriteInspection
    target_commit: TargetCommit


class FrameMoveResult(FrameEditEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa frame move"] = "spa frame move"
    persisted_reopen_verified: Literal[True]
    sprite: SpriteInspection
    target_commit: TargetCommit


class FrameRemoveResult(FrameEditEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa frame remove"] = "spa frame remove"
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
    required_capabilities=["aseprite_sprite_inspection", "aseprite_frame_authoring"],
)
FRAME_EDIT_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_frame_editing"],
)
FRAME_SUPPORT_RESOURCE = PackagedResource("frame", "document/frame/frame_support.lua")
FRAME_GET_HANDLER = PackagedHandler(
    "frame_get",
    "document/frame/frame_get.lua",
    (*SPRITE_INSPECTION_RESOURCES, FRAME_SUPPORT_RESOURCE, EFFECTIVE_PALETTE_RESOURCE),
)
FRAME_MUTATE_HANDLER = PackagedHandler(
    "frame_mutate",
    "document/frame/frame_mutate.lua",
    (
        *SPRITE_INSPECTION_RESOURCES,
        SPRITE_PERSISTENCE_RESOURCE,
        FRAME_SUPPORT_RESOURCE,
        EFFECTIVE_PALETTE_RESOURCE,
        DIGEST_RESOURCE,
    ),
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
    return validate_frame_sequence(
        sprite.frames, sprite.metadata.frame_count, invocation
    )


def validate_frame_sequence(
    frames: list[FrameFacts] | None,
    declared_count: int,
    invocation: KernelInvocationResult,
) -> list[FrameFacts]:
    if (
        frames is None
        or len(frames) != declared_count
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
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        FRAME_GET_HANDLER,
        {"sprite_file": request.sprite_file, "frame_number": request.frame_number},
        request.timeout_seconds,
    )
    try:
        frame = validate_frame_get_result(
            invocation.payload, request.frame_number, invocation, ["frame_number"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Frame Get handler returned invalid Frame facts",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc
    return FrameGetResult(sprite_file=request.sprite_file, frame=frame)


def validate_frame_get_result(
    result: dict[str, Any],
    frame_number: int,
    invocation: KernelInvocationResult,
    location: list[str | int],
) -> FrameFacts:
    count = result["frame_count"]
    if type(count) is not int or count < 1:
        raise ValueError("Frame Get has invalid Frame count")
    frames = [FrameFacts.model_validate(value) for value in result["frames"]]
    validate_frame_sequence(frames, count, invocation)
    found = result["found"]
    if type(found) is not bool:
        raise ValueError("Frame Get has invalid found flag")
    if not found:
        if frame_number <= count or result["frame"] is not None:
            raise ValueError("Frame Get missing target contradicts Frame facts")
        raise RequestIssue(
            [
                ValidationIssue(
                    location=location,
                    code="frame_not_found",
                    message="Frame Number is outside the Sprite timeline",
                )
            ]
        )
    frame = FrameFacts.model_validate(result["frame"])
    if frame_number > count or frame != frames[frame_number - 1]:
        raise RuntimeIssue(
            "postcondition_failed",
            "Frame Get address differs from Frame facts",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="selected Frame differs from Frame inspection",
            ),
            invocation.diagnostics,
        )
    return frame


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
            isinstance(input, FrameAddInput)
            and (
                evidence.background_fill != input.background_color
                or evidence.cel_relationships
                or evidence.inserted_cel_count
                != (1 if input.background_color is not None else 0)
            )
        )
        or (
            isinstance(input, FrameDuplicateInput)
            and (
                evidence.source_cel_count != evidence.inserted_cel_count
                or evidence.background_fill is not None
                or len(evidence.cel_relationships) != evidence.inserted_cel_count
                or len({tuple(item.layer_path) for item in evidence.cel_relationships})
                != evidence.inserted_cel_count
                or any(
                    item.kind != input.cel_mode
                    or item.source_frame_number != input.source_frame_number
                    for item in evidence.cel_relationships
                )
            )
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


def validate_frame_edit_evidence(
    request: FrameSetRequest | FrameMoveRequest | FrameRemoveRequest,
    evidence: FrameEditEvidence,
    sprite: SpriteInspection,
    invocation: KernelInvocationResult,
) -> None:
    validated_scope(
        SpriteGetRequest(
            sprite_file=request.source_sprite_file,
            inspection_scope=list(INSPECTION_SECTIONS),
        ),
        evidence.before,
        invocation,
    )
    before_frames = evidence.before.frames
    after_frames = sprite.frames
    if before_frames is None or after_frames is None:
        raise ValueError("Frame edit requires complete Frame facts")
    count = len(before_frames)
    expected: list[FrameNumberChange] = []
    for number in range(1, count + 1):
        after_number: int | None = number
        if isinstance(request, FrameMoveRequest):
            source, target = request.source_frame_number, request.target_frame_number
            if number == source:
                after_number = target
            elif source < number <= target:
                after_number = number - 1
            elif target <= number < source:
                after_number = number + 1
        elif isinstance(request, FrameRemoveRequest):
            if number == request.frame_number:
                after_number = None
            elif number > request.frame_number:
                after_number = number - 1
        if after_number != number:
            expected.append(
                FrameNumberChange(
                    before_frame_number=number,
                    after_frame_number=after_number,
                )
            )
        if after_number is not None:
            duration = before_frames[number - 1].duration_ms
            if isinstance(request, FrameSetRequest) and number == request.frame_number:
                duration = request.duration_ms
            if (
                after_number > len(after_frames)
                or after_frames[after_number - 1].duration_ms != duration
            ):
                raise RuntimeIssue(
                    "postcondition_failed",
                    "Persisted Frame duration differs from the request",
                    PostconditionEvidence(
                        response_path=invocation.response_path,
                        reason="Frame duration or renumbering disagrees",
                    ),
                    invocation.diagnostics,
                )
    if (
        evidence.frame_number_changes != expected
        or len(after_frames) != count - isinstance(request, FrameRemoveRequest)
        or (
            isinstance(request, FrameSetRequest)
            and any(
                getattr(evidence.before, section) != getattr(sprite, section)
                for section in (
                    "cels",
                    "tags",
                    "slices",
                    "palettes",
                    "layers",
                    "tilesets",
                )
            )
        )
    ):
        raise RuntimeIssue(
            "postcondition_failed",
            "Persisted Sprite differs from Frame edit evidence",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="Frame mapping or unchanged structures disagree",
            ),
            invocation.diagnostics,
        )


def _mutate(
    request: FrameAddRequest
    | FrameDuplicateRequest
    | FrameSetRequest
    | FrameMoveRequest
    | FrameRemoveRequest,
    services: OperationServices,
    operation: Literal["add", "duplicate", "set", "move", "remove"],
) -> (
    FrameAddResult
    | FrameDuplicateResult
    | FrameSetResult
    | FrameMoveResult
    | FrameRemoveResult
):
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
    input_fields = {
        "add": FrameAddInput,
        "duplicate": FrameDuplicateInput,
        "set": FrameSetInput,
        "move": FrameMoveInput,
        "remove": FrameRemoveInput,
    }[operation].model_fields
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
            evidence_type = (
                FrameMutationEvidence
                if operation in ("add", "duplicate")
                else FrameEditEvidence
            )
            evidence = evidence_type.model_validate(
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
        if isinstance(evidence, FrameMutationEvidence):
            assert isinstance(request, (FrameAddRequest, FrameDuplicateRequest))
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
        if isinstance(evidence, FrameEditEvidence):
            assert isinstance(
                request, (FrameSetRequest, FrameMoveRequest, FrameRemoveRequest)
            )
            validate_frame_edit_evidence(request, evidence, sprite, invocation)
        else:
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
                or (
                    isinstance(request, FrameDuplicateRequest)
                    and {tuple(item.layer_path) for item in evidence.cel_relationships}
                    != {
                        tuple(cel.layer_path)
                        for cel in cels
                        if cel.frame_number == number
                    }
                )
                or any(
                    adjustment.tag_number > len(tags)
                    or tags[adjustment.tag_number - 1].name != adjustment.name
                    or tags[adjustment.tag_number - 1].from_frame
                    != adjustment.after_from_frame
                    or tags[adjustment.tag_number - 1].to_frame
                    != adjustment.after_to_frame
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
        if operation == "duplicate":
            return FrameDuplicateResult.model_validate(result)
        if operation == "set":
            return FrameSetResult.model_validate(result)
        if operation == "move":
            return FrameMoveResult.model_validate(result)
        return FrameRemoveResult.model_validate(result)
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


def set_frame(request: FrameSetRequest, services: OperationServices) -> FrameSetResult:
    result = _mutate(request, services, "set")
    assert isinstance(result, FrameSetResult)
    return result


def move_frame(
    request: FrameMoveRequest, services: OperationServices
) -> FrameMoveResult:
    result = _mutate(request, services, "move")
    assert isinstance(result, FrameMoveResult)
    return result


def remove_frame(
    request: FrameRemoveRequest, services: OperationServices
) -> FrameRemoveResult:
    result = _mutate(request, services, "remove")
    assert isinstance(result, FrameRemoveResult)
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
    OperationDescriptor(
        "frame set",
        FrameSetRequest,
        FrameSetResult,
        set_frame,
        lambda result: result.target_commit.target_sprite_file,
        FRAME_EDIT_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        probe_before_execute=False,
    ),
    OperationDescriptor(
        "frame move",
        FrameMoveRequest,
        FrameMoveResult,
        move_frame,
        lambda result: result.target_commit.target_sprite_file,
        FRAME_EDIT_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        probe_before_execute=False,
    ),
    OperationDescriptor(
        "frame remove",
        FrameRemoveRequest,
        FrameRemoveResult,
        remove_frame,
        lambda result: result.target_commit.target_sprite_file,
        FRAME_EDIT_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        probe_before_execute=False,
    ),
)
