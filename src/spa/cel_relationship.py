"""Native Cel placement and shared Image relationships."""

from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.cel import (
    CEL_SELECT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    CelAddress,
    CelState,
    _reject,
)
from spa.contracts import PublicModel, RuntimeRequest, RuntimeRequirements
from spa.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    source_target_identity_issue,
    validate_native_sprite_path,
)
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
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
from spa.raster import Point
from spa.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteGetRequest,
    SpriteInspection,
    validated_scope,
)


class CelRelationshipRequest(RuntimeRequest):
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
    def validate_commit_intent(self) -> "CelRelationshipRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class CelPosition(Point):
    x: int = Field(ge=-32768, le=32767, strict=True)
    y: int = Field(ge=-32768, le=32767, strict=True)


class CelSetInput(PublicModel):
    target: CelAddress
    position: CelPosition | None = None
    opacity: int | None = Field(default=None, ge=0, le=255, strict=True)
    z_index: int | None = Field(default=None, ge=-32768, le=32767, strict=True)

    @model_validator(mode="after")
    def require_change(self) -> "CelSetInput":
        if self.position is None and self.opacity is None and self.z_index is None:
            raise ValueError("Specify at least one Cel property")
        return self


class CelSetRequest(CelRelationshipRequest, CelSetInput):
    pass


class CelPairRequest(CelRelationshipRequest):
    source: CelAddress
    destination: CelAddress


class CelCopyRequest(CelPairRequest):
    pass


class CelLinkRequest(CelPairRequest):
    pass


class CelUnlinkRequest(CelRelationshipRequest):
    target: CelAddress


class CelRelationshipChangeEvidence(PublicModel):
    before_cel_count: int = Field(ge=0)
    before_cels: list[CelState] = Field(min_length=1)
    affected_cels: list[CelState] = Field(min_length=1)
    cel: CelState


class CelRelationshipEvidence(CelRelationshipChangeEvidence):
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]


class CelRelationshipResult(CelRelationshipEvidence):
    target_commit: TargetCommit


class CelSetResult(CelRelationshipResult):
    status: Literal["success"] = "success"
    operation: Literal["spa cel set"] = "spa cel set"


class CelCopyResult(CelRelationshipResult):
    status: Literal["success"] = "success"
    operation: Literal["spa cel copy"] = "spa cel copy"


class CelLinkResult(CelRelationshipResult):
    status: Literal["success"] = "success"
    operation: Literal["spa cel link"] = "spa cel link"


class CelUnlinkResult(CelRelationshipResult):
    status: Literal["success"] = "success"
    operation: Literal["spa cel unlink"] = "spa cel unlink"


CEL_RELATIONSHIP_RESOURCE = PackagedResource(
    "cel_relationship", "cel_relationship_support.lua"
)
CEL_RELATIONSHIP_HANDLER = PackagedHandler(
    "cel_relationship",
    (
        SPRITE_INSPECTION_RESOURCE,
        SPRITE_PERSISTENCE_RESOURCE,
        CEL_SELECT_RESOURCE,
        CEL_SUPPORT_RESOURCE,
        CEL_RELATIONSHIP_RESOURCE,
        PackagedResource("digest", "digest.lua"),
    ),
)
CEL_RELATIONSHIP_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_cel_relationships"],
)


def _address_of(cel: CelState) -> tuple[tuple[int, ...], int]:
    return tuple(cel.layer_path), cel.frame_number


def validate_relationship_evidence(
    request: CelSetInput | CelCopyRequest | CelLinkRequest | CelUnlinkRequest,
    evidence: CelRelationshipChangeEvidence,
    invocation: KernelInvocationResult,
    operation: Literal["set", "copy", "link", "unlink"],
) -> None:
    addressed = (
        request.destination if isinstance(request, CelPairRequest) else request.target
    )
    before_keys = [_address_of(cel) for cel in evidence.before_cels]
    affected_keys = [_address_of(cel) for cel in evidence.affected_cels]
    target_key = _address_of(evidence.cel)
    expected_count = evidence.before_cel_count + int(operation in ("copy", "link"))
    prior = {_address_of(cel): cel for cel in evidence.before_cels}
    current = {_address_of(cel): cel for cel in evidence.affected_cels}
    source_key = (
        (tuple(request.source.layer.layer_path), request.source.frame_number)
        if isinstance(request, CelPairRequest)
        and request.source.layer.layer_path is not None
        else None
    )
    if (
        not evidence.cel.exists
        or target_key not in affected_keys
        or target_key not in prior
        or evidence.cel != current[target_key]
        or len(before_keys) != len(set(before_keys))
        or len(affected_keys) != len(set(affected_keys))
        or (
            addressed.layer.layer_path is not None
            and evidence.cel.layer_path != addressed.layer.layer_path
        )
        or evidence.cel.frame_number != addressed.frame_number
        or not set(affected_keys).issubset(before_keys)
        or evidence.before_cel_count < sum(cel.exists for cel in prior.values())
        or (
            isinstance(evidence, CelRelationshipEvidence)
            and evidence.sprite.metadata.cel_count != expected_count
        )
        or (operation in ("copy", "link") and prior[target_key].exists)
        or (operation in ("set", "unlink") and not prior[target_key].exists)
        or (operation == "copy" and evidence.cel.linked_cels)
        or (operation == "copy" and set(affected_keys) != {target_key})
        or (operation == "unlink" and evidence.cel.linked_cels)
        or (
            operation == "link"
            and (
                source_key is not None
                and source_key
                not in {
                    (tuple(link.layer_path), link.frame_number)
                    for link in evidence.cel.linked_cels
                }
            )
        )
    ):
        raise RuntimeIssue(
            "postcondition_failed",
            "Cel relationship evidence differs from the request",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="Cel address, existence, count, or affected scope disagrees",
            ),
            invocation.diagnostics,
        )


def _mutate(
    request: CelSetRequest | CelCopyRequest | CelLinkRequest | CelUnlinkRequest,
    services: OperationServices,
    operation: Literal["set", "copy", "link", "unlink"],
) -> CelSetResult | CelCopyResult | CelLinkResult | CelUnlinkResult:
    source = Path(request.source_sprite_file)
    target_file = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files, source, target_file, request.in_place
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    observation = services.probe_runtime(request)
    staged = services.target_files.staged_path(target_file)
    payload: dict[str, object] = {
        "operation": operation,
        "source_sprite_file": request.source_sprite_file,
        "staged_sprite_file": str(staged),
    }
    address_role: Literal["target", "source", "destination"] = "target"
    if isinstance(request, CelPairRequest):
        payload["source"] = request.source.model_dump(mode="json", exclude_none=True)
        payload["destination"] = request.destination.model_dump(
            mode="json", exclude_none=True
        )
        addressed = request.destination
    else:
        payload["target"] = request.target.model_dump(mode="json", exclude_none=True)
        addressed = request.target
    if isinstance(request, CelSetRequest):
        payload["changes"] = request.model_dump(
            include={"position", "opacity", "z_index"}, exclude_none=True
        )
    try:
        invocation = services.invoke_kernel(
            observation, CEL_RELATIONSHIP_HANDLER, payload, request.timeout_seconds
        )
        rejected = invocation.payload.get("rejection")
        if isinstance(rejected, dict) and isinstance(request, CelPairRequest):
            role = rejected.get("role")
            if role not in ("source", "destination"):
                raise RuntimeIssue(
                    "response_malformed",
                    "Packaged Cel handler returned an invalid address role",
                    ResponseEvidence(response_path=invocation.response_path),
                    invocation.diagnostics,
                )
            address_role = role
            addressed = request.source if role == "source" else request.destination
        _reject(
            invocation,
            addressed.layer,
            addressed,
            (addressed.frame_number, addressed.frame_number),
            address_role=address_role,
        )
        try:
            evidence = CelRelationshipEvidence.model_validate(invocation.payload)
        except (TypeError, ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Packaged Cel handler returned invalid relationship evidence: {exc}",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        validated_scope(
            SpriteGetRequest(
                sprite_file=request.target_sprite_file,
                inspection_scope=list(INSPECTION_SECTIONS),
            ),
            evidence.sprite,
            invocation,
        )
        validate_relationship_evidence(request, evidence, invocation, operation)
        identity_issue = source_target_identity_issue(
            services.target_files, source, target_file, request.in_place
        )
        if identity_issue is not None:
            raise RuntimeIssue(
                "target_commit_failed",
                "Source/Target publication identity changed before Target Commit",
                TargetCommitEvidence(
                    str(target_file), "source_target_identity_changed"
                ),
            )
        committed = services.target_files.commit(
            staged, target_file, overwrite=request.overwrite
        )
        fields = {
            **evidence.model_dump(),
            "target_commit": TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
        }
        return {
            "set": CelSetResult,
            "copy": CelCopyResult,
            "link": CelLinkResult,
            "unlink": CelUnlinkResult,
        }[operation].model_validate(fields)
    finally:
        services.target_files.discard(staged)


def set_cel(request: CelSetRequest, services: OperationServices) -> CelSetResult:
    result = _mutate(request, services, "set")
    assert isinstance(result, CelSetResult)
    return result


def copy_cel(request: CelCopyRequest, services: OperationServices) -> CelCopyResult:
    result = _mutate(request, services, "copy")
    assert isinstance(result, CelCopyResult)
    return result


def link_cel(request: CelLinkRequest, services: OperationServices) -> CelLinkResult:
    result = _mutate(request, services, "link")
    assert isinstance(result, CelLinkResult)
    return result


def unlink_cel(
    request: CelUnlinkRequest, services: OperationServices
) -> CelUnlinkResult:
    result = _mutate(request, services, "unlink")
    assert isinstance(result, CelUnlinkResult)
    return result


_CEL_MUTATION_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    "layer_missing",
    "layer_ambiguous",
    "layer_invalid_path",
    "layer_uuid_unpersisted",
    "cel_frame_out_of_bounds",
    "cel_unsupported_target",
    "cel_not_found",
    "target_commit_failed",
)

CEL_RELATIONSHIP_OPERATIONS = (
    OperationDescriptor(
        "cel set",
        CelSetRequest,
        CelSetResult,
        set_cel,
        lambda result: result.target_commit.target_sprite_file,
        CEL_RELATIONSHIP_REQUIREMENTS,
        _CEL_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        plan_eligible=True,
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "cel copy",
        CelCopyRequest,
        CelCopyResult,
        copy_cel,
        lambda result: result.target_commit.target_sprite_file,
        CEL_RELATIONSHIP_REQUIREMENTS,
        (*_CEL_MUTATION_FAILURE_CODES, "cel_already_exists"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "cel link",
        CelLinkRequest,
        CelLinkResult,
        link_cel,
        lambda result: result.target_commit.target_sprite_file,
        CEL_RELATIONSHIP_REQUIREMENTS,
        (*_CEL_MUTATION_FAILURE_CODES, "cel_already_exists"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "cel unlink",
        CelUnlinkRequest,
        CelUnlinkResult,
        unlink_cel,
        lambda result: result.target_commit.target_sprite_file,
        CEL_RELATIONSHIP_REQUIREMENTS,
        _CEL_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
