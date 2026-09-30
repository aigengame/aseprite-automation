"""Stored Tag facts and exact current-snapshot Tag addressing."""

from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.authoring.document.sprite import (
    SPRITE_GET_HANDLER,
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteInspection,
    TagDirection,
    TagFacts,
    _inspection_from_kernel,
)
from spa.contracts.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    source_target_identity_issue,
    validate_native_sprite_path,
)
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationIssue,
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
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.contracts.raster import RgbaColor


def reject_nul_in_name(value: str | None) -> str | None:
    if value is not None and "\x00" in value:
        raise ValueError("Tag name cannot contain NUL")
    return value


class TagAddress(PublicModel):
    """Exactly one index or unique name in the current Sprite.tags snapshot."""

    tag_index: int | None = Field(default=None, ge=1, strict=True)
    tag_name: str | None = None

    _validate_name = field_validator("tag_name")(reject_nul_in_name)

    @model_validator(mode="after")
    def exactly_one(self) -> "TagAddress":
        if (self.tag_index is None) == (self.tag_name is None):
            raise ValueError("Specify exactly one Tag address")
        return self


class TagTargetDetails(PublicModel):
    kind: Literal["tag_target"] = "tag_target"
    address: TagAddress


class TagRangeDetails(PublicModel):
    kind: Literal["tag_range"] = "tag_range"
    from_frame: int
    to_frame: int
    frame_count: int = Field(ge=1)


TAG_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "tag_missing", "No Tag matches the address", "input", TagTargetDetails
    ),
    FailureCodeSpec(
        "tag_ambiguous", "More than one Tag matches the name", "input", TagTargetDetails
    ),
    FailureCodeSpec(
        "tag_range_out_of_bounds",
        "Tag range is outside the current Sprite timeline",
        "input",
        TagRangeDetails,
    ),
)


class TagListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)

    _validate_sprite = field_validator("sprite_file")(validate_native_sprite_path)


class TagGetRequest(TagListRequest):
    target: TagAddress


class _TagMutationRequest(RuntimeRequest):
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
    def validate_commit_intent(self) -> "_TagMutationRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class TagAddRequest(_TagMutationRequest):
    name: str
    from_frame: int = Field(ge=1, strict=True)
    to_frame: int = Field(ge=1, strict=True)
    direction: TagDirection
    repeats: int = Field(ge=0, le=65535, strict=True)
    color: RgbaColor | None = None

    _validate_name = field_validator("name")(reject_nul_in_name)

    @model_validator(mode="after")
    def validate_range(self) -> "TagAddRequest":
        if self.from_frame > self.to_frame:
            raise ValueError("Tag range must be ordered and inclusive")
        return self


class TagSetProperties(PublicModel):
    name: str | None = None
    from_frame: int | None = Field(default=None, ge=1, strict=True)
    to_frame: int | None = Field(default=None, ge=1, strict=True)
    direction: TagDirection | None = None
    repeats: int | None = Field(default=None, ge=0, le=65535, strict=True)
    color: RgbaColor | None = None

    _validate_name = field_validator("name")(reject_nul_in_name)

    @model_validator(mode="after")
    def require_patch(self) -> "TagSetProperties":
        if not self.model_fields_set:
            raise ValueError("Set requires at least one Tag property")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Set properties cannot be null")
        if (
            self.from_frame is not None
            and self.to_frame is not None
            and self.from_frame > self.to_frame
        ):
            raise ValueError("Tag range must be ordered and inclusive")
        return self


class _AddressedMutationRequest(_TagMutationRequest):
    target: TagAddress


class TagSetRequest(_AddressedMutationRequest):
    properties: TagSetProperties


class TagRemoveRequest(_AddressedMutationRequest):
    pass


class IndexedTagFacts(TagFacts):
    tag_index: int = Field(ge=1, strict=True)


class TagListResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tag list"] = "spa tag list"
    sprite_file: str
    tags: list[IndexedTagFacts]


class TagGetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa tag get"] = "spa tag get"
    sprite_file: str
    tag: IndexedTagFacts


class _TagMutationResult(PublicModel):
    status: Literal["success"] = "success"
    target_commit: TargetCommit
    persisted_reopen_verified: Literal[True]
    tags: list[IndexedTagFacts]


class TagAddResult(_TagMutationResult):
    operation: Literal["spa tag add"] = "spa tag add"
    tag: IndexedTagFacts


class TagSetResult(_TagMutationResult):
    operation: Literal["spa tag set"] = "spa tag set"
    tag: IndexedTagFacts


class TagRemoveResult(_TagMutationResult):
    operation: Literal["spa tag remove"] = "spa tag remove"
    removed_tag: IndexedTagFacts


TAG_READ_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection"],
)
TAG_MUTATION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_tag_authoring"],
)
TAG_SELECT_RESOURCE = PackagedResource("tag_select", "tag_select.lua")
TAG_GET_HANDLER = PackagedHandler(
    "tag_get", (SPRITE_INSPECTION_RESOURCE, TAG_SELECT_RESOURCE)
)
TAG_MUTATE_HANDLER = PackagedHandler(
    "tag_mutate",
    (
        SPRITE_INSPECTION_RESOURCE,
        SPRITE_PERSISTENCE_RESOURCE,
        PackagedResource("digest", "digest.lua"),
        PackagedResource("tag", "tag_support.lua"),
        TAG_SELECT_RESOURCE,
    ),
)


def _indexed(tags: list[TagFacts]) -> list[IndexedTagFacts]:
    return [
        IndexedTagFacts.model_validate({**tag.model_dump(), "tag_index": index})
        for index, tag in enumerate(tags, 1)
    ]


def _read_tags(
    request: TagListRequest, services: OperationServices
) -> list[IndexedTagFacts]:
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        SPRITE_GET_HANDLER,
        {"sprite_file": request.sprite_file, "inspection_scope": ["tags"]},
        request.timeout_seconds,
    )
    sprite = _inspection_from_kernel(invocation)
    if sprite.tags is None or len(sprite.tags) != sprite.metadata.tag_count:
        raise RuntimeIssue(
            "postcondition_failed",
            "Tag inspection is incomplete",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="Tag count differs from inspection metadata",
            ),
            invocation.diagnostics,
        )
    return _indexed(sprite.tags)


def list_tags(request: TagListRequest, services: OperationServices) -> TagListResult:
    return TagListResult(
        sprite_file=request.sprite_file, tags=_read_tags(request, services)
    )


def get_tag(request: TagGetRequest, services: OperationServices) -> TagGetResult:
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        TAG_GET_HANDLER,
        {
            "sprite_file": request.sprite_file,
            "target": request.target.model_dump(exclude_none=True),
        },
        request.timeout_seconds,
    )
    _reject(invocation, request.target)
    try:
        sprite = SpriteInspection.model_validate(invocation.payload["sprite"])
        index = invocation.payload["selected_index"]
        if (
            sprite.tags is None
            or len(sprite.tags) != sprite.metadata.tag_count
            or type(index) is not int
            or index < 1
            or index > len(sprite.tags)
        ):
            raise ValueError("Tag Get evidence disagrees with Sprite inspection")
        selected = _indexed(sprite.tags)[index - 1]
        if (
            request.target.tag_index is not None and request.target.tag_index != index
        ) or (
            request.target.tag_name is not None
            and request.target.tag_name != selected.name
        ):
            raise ValueError("Tag Get address differs from selected Tag facts")
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Tag Get handler returned invalid Tag facts",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc
    return TagGetResult(sprite_file=request.sprite_file, tag=selected)


def _reject(invocation: KernelInvocationResult, address: TagAddress | None) -> None:
    rejection = invocation.payload.get("rejection")
    if rejection is None:
        return
    if isinstance(rejection, dict) and isinstance(rejection.get("message"), str):
        if rejection.get("code") in ("tag_missing", "tag_ambiguous") and address:
            raise OperationIssue(
                rejection["code"],
                rejection["message"],
                TagTargetDetails(address=address),
            )
        if rejection.get("code") == "tag_range_out_of_bounds":
            try:
                details = TagRangeDetails.model_validate(rejection["details"])
            except (KeyError, ValidationError, TypeError):
                pass
            else:
                raise OperationIssue(rejection["code"], rejection["message"], details)
    raise RuntimeIssue(
        "response_malformed",
        "Packaged Tag handler returned invalid rejection",
        ResponseEvidence(response_path=invocation.response_path),
        invocation.diagnostics,
    )


def _mutate(
    request: TagAddRequest | TagSetRequest | TagRemoveRequest,
    services: OperationServices,
    operation: Literal["add", "set", "remove"],
) -> TagAddResult | TagSetResult | TagRemoveResult:
    source = Path(request.source_sprite_file)
    target = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files, source, target, request.in_place
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    observation = services.probe_runtime(request)
    staged = services.target_files.staged_path(target)
    payload: dict[str, object] = {
        "operation": operation,
        "source_sprite_file": request.source_sprite_file,
        "staged_sprite_file": str(staged),
    }
    address = request.target if isinstance(request, _AddressedMutationRequest) else None
    if address is not None:
        payload["target"] = address.model_dump(exclude_none=True)
    if isinstance(request, TagAddRequest):
        payload["properties"] = request.model_dump(
            mode="json",
            include={"name", "from_frame", "to_frame", "direction", "repeats", "color"},
            exclude_none=True,
        )
    elif isinstance(request, TagSetRequest):
        payload["properties"] = request.properties.model_dump(
            mode="json", exclude_unset=True
        )
    try:
        invocation = services.invoke_kernel(
            observation, TAG_MUTATE_HANDLER, payload, request.timeout_seconds
        )
        _reject(invocation, address)
        try:
            sprite = SpriteInspection.model_validate(invocation.payload["sprite"])
            if sprite.tags is None or len(sprite.tags) != sprite.metadata.tag_count:
                raise ValueError("Tag inspection is incomplete")
            tags = _indexed(sprite.tags)
            before_count = invocation.payload["before_tag_count"]
            if type(before_count) is not int or before_count < 0:
                raise ValueError("invalid prior Tag count")
            selected = IndexedTagFacts.model_validate(invocation.payload["tag"])
            verified = invocation.payload["persisted_reopen_verified"]
            if verified is not True:
                raise ValueError("persisted reopen was not verified")
            expected_count = (
                before_count + {"add": 1, "set": 0, "remove": -1}[operation]
            )
            if len(tags) != expected_count:
                raise ValueError("Tag count differs from mutation")
            if operation == "remove":
                if selected.tag_index > before_count:
                    raise ValueError("removed Tag index is out of range")
            elif (
                selected.tag_index > len(tags)
                or tags[selected.tag_index - 1] != selected
            ):
                raise ValueError("selected Tag differs from reopened Sprite")
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "postcondition_failed",
                "Persisted Tag evidence is incomplete or inconsistent",
                PostconditionEvidence(
                    response_path=invocation.response_path,
                    reason="Tag mutation evidence disagrees with reopened Sprite",
                ),
                invocation.diagnostics,
            ) from exc
        identity_issue = source_target_identity_issue(
            services.target_files, source, target, request.in_place
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
        fields = {
            "target_commit": TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
            "persisted_reopen_verified": True,
            "tags": tags,
        }
        if operation == "add":
            return TagAddResult(tag=selected, **fields)
        if operation == "set":
            return TagSetResult(tag=selected, **fields)
        return TagRemoveResult(removed_tag=selected, **fields)
    finally:
        services.target_files.discard(staged)


def add_tag(request: TagAddRequest, services: OperationServices) -> TagAddResult:
    result = _mutate(request, services, "add")
    assert isinstance(result, TagAddResult)
    return result


def set_tag(request: TagSetRequest, services: OperationServices) -> TagSetResult:
    result = _mutate(request, services, "set")
    assert isinstance(result, TagSetResult)
    return result


def remove_tag(
    request: TagRemoveRequest, services: OperationServices
) -> TagRemoveResult:
    result = _mutate(request, services, "remove")
    assert isinstance(result, TagRemoveResult)
    return result


TAG_OPERATIONS = (
    OperationDescriptor(
        "tag list",
        TagListRequest,
        TagListResult,
        list_tags,
        lambda result: f"{len(result.tags)} Tags",
        TAG_READ_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
    OperationDescriptor(
        "tag get",
        TagGetRequest,
        TagGetResult,
        get_tag,
        lambda result: f"Tag {result.tag.tag_index}: {result.tag.name}",
        TAG_READ_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "tag_missing", "tag_ambiguous"),
    ),
    OperationDescriptor(
        "tag add",
        TagAddRequest,
        TagAddResult,
        add_tag,
        lambda result: result.target_commit.target_sprite_file,
        TAG_MUTATION_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "tag_range_out_of_bounds", "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "tag set",
        TagSetRequest,
        TagSetResult,
        set_tag,
        lambda result: result.target_commit.target_sprite_file,
        TAG_MUTATION_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "tag_missing",
            "tag_ambiguous",
            "tag_range_out_of_bounds",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "tag remove",
        TagRemoveRequest,
        TagRemoveResult,
        remove_tag,
        lambda result: result.target_commit.target_sprite_file,
        TAG_MUTATION_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "tag_missing",
            "tag_ambiguous",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
