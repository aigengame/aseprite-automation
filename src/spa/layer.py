"""Layer hierarchy, exact current addresses, and structural addition."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.contracts import (
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    source_target_identity_issue,
    validate_native_sprite_path,
)
from spa.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.ports import (
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
from spa.sprite import (
    LayerFacts,
    SpriteGetRequest,
    SpriteGetResult,
    SpriteInspection,
    get_sprite,
    validated_scope,
)

OneBasedIndex = Annotated[int, Field(ge=1)]


class LayerAddress(PublicModel):
    """One exact current path, persisted UUID, or unique Sprite-wide name."""

    layer_path: list[OneBasedIndex] | None = Field(default=None, min_length=1)
    layer_uuid: str | None = Field(default=None, min_length=1)
    layer_name: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def exactly_one(self) -> "LayerAddress":
        if (
            sum(
                value is not None
                for value in (self.layer_path, self.layer_uuid, self.layer_name)
            )
            != 1
        ):
            raise ValueError("Specify exactly one Layer address")
        return self


class LayerTargetDetails(PublicModel):
    kind: Literal["layer_target"] = "layer_target"
    address_role: Literal["target", "parent"]
    address: LayerAddress


LAYER_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "layer_missing", "No Layer matches the address", "input", LayerTargetDetails
    ),
    FailureCodeSpec(
        "layer_ambiguous",
        "More than one Layer matches the name",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_invalid_path",
        "The path does not locate a Layer in the current hierarchy",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_uuid_unpersisted",
        "The Sprite does not persist the addressed Layer UUID",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_parent_not_group",
        "The selected parent is not a Group Layer",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_unsupported_target",
        "The selected Layer does not support the requested mutation",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_invalid_position",
        "The requested position is invalid for the selected Layer's parent",
        "input",
        LayerTargetDetails,
    ),
)
LAYER_TARGET_FAILURE_CODES = tuple(spec.code for spec in LAYER_FAILURE_CODE_SPECS)
LAYER_ADDRESS_FAILURE_CODES = LAYER_TARGET_FAILURE_CODES[:4]


class LayerListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)

    _validate_source = field_validator("sprite_file")(validate_native_sprite_path)


class LayerGetRequest(LayerListRequest):
    target: LayerAddress


class LayerAddRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    kind: Literal["transparent", "group"]
    name: str = Field(min_length=1)
    parent: LayerAddress | None = None

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_commit_intent(self) -> "LayerAddRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


BlendModeName = Literal[
    "normal",
    "multiply",
    "screen",
    "overlay",
    "darken",
    "lighten",
    "color_dodge",
    "color_burn",
    "hard_light",
    "soft_light",
    "difference",
    "exclusion",
    "hsl_hue",
    "hsl_saturation",
    "hsl_color",
    "hsl_luminosity",
    "addition",
    "subtract",
    "divide",
]


class LayerSetProperties(PublicModel):
    name: str | None = Field(default=None, min_length=1)
    is_visible: bool | None = None
    is_editable: bool | None = None
    opacity: int | None = Field(default=None, ge=0, le=255, strict=True)
    blend_mode: BlendModeName | None = None

    @model_validator(mode="after")
    def require_patch(self) -> "LayerSetProperties":
        if not self.model_fields_set:
            raise ValueError("Set requires at least one Layer property")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Set properties cannot be null")
        return self


class _LayerMutationRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    target: LayerAddress

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_commit_intent(self) -> "_LayerMutationRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class LayerSetRequest(_LayerMutationRequest):
    properties: LayerSetProperties


class LayerMoveRequest(_LayerMutationRequest):
    stack_index: int = Field(ge=1, strict=True)


class LayerRemoveRequest(_LayerMutationRequest):
    pass


class LayerMergeRequest(_LayerMutationRequest):
    pass


class LayerListResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa layer list"] = "spa layer list"
    sprite_file: str
    use_layer_uuids: bool
    layers: list[LayerFacts]


class LayerGetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa layer get"] = "spa layer get"
    sprite_file: str
    use_layer_uuids: bool
    layer: LayerFacts


class LayerAddResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa layer add"] = "spa layer add"
    target_commit: TargetCommit
    persisted_reopen_verified: Literal[True]
    use_layer_uuids: bool
    layer: LayerFacts


class LayerAffectedCel(PublicModel):
    layer_path: list[OneBasedIndex] = Field(min_length=1)
    frame_number: int = Field(ge=1, strict=True)


class LayerAffectedSet(PublicModel):
    layer_paths: list[list[OneBasedIndex]]
    cels: list[LayerAffectedCel]


class LayerRenderedFrame(PublicModel):
    frame_number: int = Field(ge=1, strict=True)
    before_digest: str = Field(pattern=r"^[0-9a-f]{16}$")
    after_digest: str = Field(pattern=r"^[0-9a-f]{16}$")


class LayerMutationEvidence(PublicModel):
    before: SpriteInspection
    after: SpriteInspection
    affected_before: LayerAffectedSet
    affected_after: LayerAffectedSet
    rendered_frames: list[LayerRenderedFrame]
    persisted_reopen_verified: bool


class _LayerMutationResult(LayerMutationEvidence):
    status: Literal["success"] = "success"
    persisted_reopen_verified: Literal[True]
    target_commit: TargetCommit


class LayerSetResult(_LayerMutationResult):
    operation: Literal["spa layer set"] = "spa layer set"


class LayerMoveResult(_LayerMutationResult):
    operation: Literal["spa layer move"] = "spa layer move"


class LayerRemoveResult(_LayerMutationResult):
    operation: Literal["spa layer remove"] = "spa layer remove"


class LayerMergeResult(_LayerMutationResult):
    operation: Literal["spa layer merge"] = "spa layer merge"


LAYER_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_layer_hierarchy"],
)
LAYER_MUTATION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_layer_mutation"],
)
LAYER_MERGE_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_layer_merge"],
)
LAYER_GET_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    *LAYER_ADDRESS_FAILURE_CODES,
)
LAYER_ADD_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    *LAYER_ADDRESS_FAILURE_CODES,
    "layer_parent_not_group",
    "target_commit_failed",
)
LAYER_MUTATION_FAILURE_CODES = (
    *RUNTIME_FAILURE_CODES,
    *(code for code in LAYER_TARGET_FAILURE_CODES if code != "layer_parent_not_group"),
    "target_commit_failed",
)
LAYER_INSPECTION_RESOURCE = PackagedResource("inspection", "sprite_inspect.lua")
LAYER_SELECT_RESOURCE = PackagedResource("layer_select", "layer_select.lua")
LAYER_GET_HANDLER = PackagedHandler(
    "layer_get", (LAYER_INSPECTION_RESOURCE, LAYER_SELECT_RESOURCE)
)
LAYER_ADD_HANDLER = PackagedHandler(
    "layer_add", (LAYER_INSPECTION_RESOURCE, LAYER_SELECT_RESOURCE)
)
LAYER_MUTATE_HANDLER = PackagedHandler(
    "layer_mutate",
    (
        LAYER_INSPECTION_RESOURCE,
        LAYER_SELECT_RESOURCE,
        PackagedResource("layer_mutation", "layer_mutation_support.lua"),
        PackagedResource("digest", "digest.lua"),
        PackagedResource("persistence", "sprite_persistence.lua"),
    ),
)


def _walk(layers: list[LayerFacts]) -> list[LayerFacts]:
    return [item for layer in layers for item in (layer, *_walk(layer.children))]


def _reject_target(
    invocation: KernelInvocationResult,
    address_role: Literal["target", "parent"],
    address: LayerAddress | None,
) -> None:
    rejection = invocation.payload.get("rejection")
    if rejection is None:
        return
    if (
        not isinstance(rejection, dict)
        or rejection.get("code") not in LAYER_TARGET_FAILURE_CODES
        or not isinstance(rejection.get("message"), str)
        or address is None
    ):
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Layer handler returned an invalid target rejection",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        )
    raise OperationIssue(
        rejection["code"],
        rejection["message"],
        LayerTargetDetails(address_role=address_role, address=address),
    )


def _kernel_inspection(invocation: KernelInvocationResult) -> SpriteInspection:
    try:
        inspection = SpriteInspection.model_validate(invocation.payload["sprite"])
    except (KeyError, TypeError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Layer handler returned invalid inspection facts",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc
    if (
        inspection.layers is None
        or len(_walk(inspection.layers)) != inspection.metadata.layer_count
    ):
        raise RuntimeIssue(
            "postcondition_failed",
            "Layer hierarchy is incomplete",
            PostconditionEvidence(
                response_path=invocation.response_path, reason="Layer count mismatch"
            ),
            invocation.diagnostics,
        )
    return inspection


def _selected_layer(
    invocation: KernelInvocationResult, inspection: SpriteInspection, field: str
) -> LayerFacts:
    path = invocation.payload.get(field)
    if (
        not isinstance(path, list)
        or not path
        or not all(type(index) is int and index >= 1 for index in path)
        or inspection.layers is None
    ):
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Layer handler returned an invalid selected path",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        )
    selected = next(
        (layer for layer in _walk(inspection.layers) if layer.path == path), None
    )
    if selected is None:
        raise RuntimeIssue(
            "postcondition_failed",
            "Selected Layer is absent from the inspected hierarchy",
            PostconditionEvidence(
                response_path=invocation.response_path, reason="selected path absent"
            ),
            invocation.diagnostics,
        )
    return selected


def _inspect(
    sprite_file: str, request: RuntimeRequest, services: OperationServices
) -> SpriteGetResult:
    return get_sprite(
        SpriteGetRequest(
            sprite_file=sprite_file,
            inspection_scope=["layers"],
            aseprite=request.aseprite,
            timeout_seconds=request.timeout_seconds,
        ),
        services,
    )


def list_layers(
    request: LayerListRequest, services: OperationServices
) -> LayerListResult:
    inspection = _inspect(request.sprite_file, request, services)
    assert inspection.layers is not None
    return LayerListResult(
        sprite_file=request.sprite_file,
        use_layer_uuids=inspection.metadata.use_layer_uuids,
        layers=inspection.layers,
    )


def get_layer(request: LayerGetRequest, services: OperationServices) -> LayerGetResult:
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        LAYER_GET_HANDLER,
        {
            "sprite_file": request.sprite_file,
            "target": request.target.model_dump(exclude_none=True),
        },
        request.timeout_seconds,
    )
    _reject_target(invocation, "target", request.target)
    inspection = _kernel_inspection(invocation)
    layer = _selected_layer(invocation, inspection, "selected_path")
    return LayerGetResult(
        sprite_file=request.sprite_file,
        use_layer_uuids=inspection.metadata.use_layer_uuids,
        layer=layer,
    )


def _reopened(invocation: KernelInvocationResult) -> tuple[SpriteInspection, list[int]]:
    try:
        inspection = _kernel_inspection(invocation)
        path = list(invocation.payload["added_path"])
        if not path or not all(isinstance(index, int) and index >= 1 for index in path):
            raise ValueError("invalid added path")
        return inspection, path
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Layer handler returned invalid reopened facts",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc


def add_layer(request: LayerAddRequest, services: OperationServices) -> LayerAddResult:
    target = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files,
        Path(request.source_sprite_file),
        target,
        request.in_place,
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    staged = services.target_files.staged_path(target)
    payload = {
        "source_sprite_file": request.source_sprite_file,
        "staged_sprite_file": str(staged),
        "kind": request.kind,
        "name": request.name,
        "inspection_scope": ["layers"],
    }
    if request.parent is not None:
        payload["parent"] = request.parent.model_dump(exclude_none=True)
    observation = services.probe_runtime(request)
    try:
        invocation = services.invoke_kernel(
            observation, LAYER_ADD_HANDLER, payload, request.timeout_seconds
        )
        _reject_target(invocation, "parent", request.parent)
        reopened, added_path = _reopened(invocation)
        try:
            before_count = invocation.payload["before_layer_count"]
            before_uuids = invocation.payload["before_use_layer_uuids"]
            if type(before_count) is not int or type(before_uuids) is not bool:
                raise TypeError("invalid before facts")
        except (KeyError, TypeError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Packaged Layer handler returned invalid before facts",
                ResponseEvidence(response_path=invocation.response_path),
                invocation.diagnostics,
            ) from exc
        if reopened.layers is None:
            raise RuntimeIssue(
                "postcondition_failed",
                "Reopened Layer hierarchy is absent",
                PostconditionEvidence(
                    response_path=invocation.response_path, reason="missing layers"
                ),
                invocation.diagnostics,
            )
        added = next(
            (layer for layer in _walk(reopened.layers) if layer.path == added_path),
            None,
        )
        valid = (
            added is not None
            and added.name == request.name
            and added.is_group == (request.kind == "group")
            and (
                request.kind == "group"
                or (
                    added.is_image
                    and not added.is_tilemap
                    and not added.is_reference
                    and not added.is_background
                )
            )
            and reopened.metadata.layer_count == before_count + 1
            and len(_walk(reopened.layers)) == reopened.metadata.layer_count
            and reopened.metadata.use_layer_uuids == before_uuids
            and (added.layer_uuid is not None) == before_uuids
        )
        if not valid:
            raise RuntimeIssue(
                "postcondition_failed",
                "Reopened Layer differs from the add request",
                PostconditionEvidence(
                    response_path=invocation.response_path,
                    reason="added Layer or UUID policy mismatch",
                ),
                invocation.diagnostics,
            )
        assert added is not None
        committed = services.target_files.commit(
            staged, target, overwrite=request.overwrite
        )
        return LayerAddResult(
            target_commit=TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
            persisted_reopen_verified=True,
            use_layer_uuids=reopened.metadata.use_layer_uuids,
            layer=added,
        )
    finally:
        services.target_files.discard(staged)


def _mutation_evidence(invocation: KernelInvocationResult) -> LayerMutationEvidence:
    try:
        return LayerMutationEvidence.model_validate(
            {
                field: invocation.payload[field]
                for field in LayerMutationEvidence.model_fields
            }
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Layer handler returned invalid mutation evidence",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc


def _validate_affected_set(
    affected: LayerAffectedSet,
    inspection: SpriteInspection,
    invocation: KernelInvocationResult,
    phase: str,
) -> None:
    assert inspection.layers is not None and inspection.cels is not None
    paths = {tuple(layer.path) for layer in _walk(inspection.layers)}
    cel_addresses = {
        (tuple(cel.layer_path), cel.frame_number) for cel in inspection.cels
    }
    affected_paths = [tuple(path) for path in affected.layer_paths]
    affected_cels = [(tuple(cel.layer_path), cel.frame_number) for cel in affected.cels]
    if (
        len(set(affected_paths)) != len(affected_paths)
        or len(set(affected_cels)) != len(affected_cels)
        or any(path not in paths for path in affected_paths)
        or any(address not in cel_addresses for address in affected_cels)
        or any(address[0] not in affected_paths for address in affected_cels)
    ):
        raise RuntimeIssue(
            "postcondition_failed",
            f"Layer {phase} affected set disagrees with Sprite inspection",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason=f"{phase} affected Layer or Cel address mismatch",
            ),
            invocation.diagnostics,
        )


def _validate_mutation_evidence(
    request: _LayerMutationRequest,
    evidence: LayerMutationEvidence,
    invocation: KernelInvocationResult,
) -> None:
    if not evidence.persisted_reopen_verified:
        raise RuntimeIssue(
            "postcondition_failed",
            "Layer mutation lacks persisted Sprite evidence",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="persisted Sprite verification is absent",
            ),
            invocation.diagnostics,
        )
    for inspection in (evidence.before, evidence.after):
        validated_scope(
            SpriteGetRequest(
                sprite_file=request.source_sprite_file,
                inspection_scope=["layers", "cels"],
            ),
            inspection,
            invocation,
        )
    before = evidence.before.metadata
    after = evidence.after.metadata
    assert evidence.before.layers is not None
    before_layers = _walk(evidence.before.layers)
    address = request.target
    addressed_layers = [
        layer
        for layer in before_layers
        if (
            (address.layer_path is not None and layer.path == address.layer_path)
            or (
                address.layer_uuid is not None
                and layer.layer_uuid == address.layer_uuid
            )
            or (address.layer_name is not None and layer.name == address.layer_name)
        )
    ]
    no_reported_change = not evidence.affected_before.layer_paths
    changed_facts_without_impact = no_reported_change and (
        evidence.before.layers != evidence.after.layers
        or evidence.before.cels != evidence.after.cels
        or any(
            frame.before_digest != frame.after_digest
            for frame in evidence.rendered_frames
        )
    )
    if (
        before.width != after.width
        or before.height != after.height
        or before.color_mode != after.color_mode
        or before.frame_count != after.frame_count
        or before.tag_count != after.tag_count
        or before.tileset_count != after.tileset_count
        or [frame.frame_number for frame in evidence.rendered_frames]
        != list(range(1, before.frame_count + 1))
        or len(addressed_layers) != 1
        or changed_facts_without_impact
        or (
            not no_reported_change
            and addressed_layers[0].path not in evidence.affected_before.layer_paths
        )
    ):
        raise RuntimeIssue(
            "postcondition_failed",
            "Layer mutation evidence omits or changes unrelated Sprite facts",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="Sprite identity, frame digests, or affected target mismatch",
            ),
            invocation.diagnostics,
        )
    _validate_affected_set(
        evidence.affected_before, evidence.before, invocation, "before"
    )
    _validate_affected_set(evidence.affected_after, evidence.after, invocation, "after")


def _mutate_layer(
    request: LayerSetRequest
    | LayerMoveRequest
    | LayerRemoveRequest
    | LayerMergeRequest,
    services: OperationServices,
    operation: Literal["set", "move", "remove", "merge"],
) -> LayerSetResult | LayerMoveResult | LayerRemoveResult | LayerMergeResult:
    target_file = Path(request.target_sprite_file)
    source_file = Path(request.source_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files, source_file, target_file, request.in_place
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    observation = services.probe_runtime(request)
    staged_file = services.target_files.staged_path(target_file)
    payload: dict[str, object] = {
        "operation": operation,
        "source_sprite_file": request.source_sprite_file,
        "staged_sprite_file": str(staged_file),
        "target": request.target.model_dump(mode="json", exclude_none=True),
    }
    if isinstance(request, LayerSetRequest):
        payload["properties"] = request.properties.model_dump(
            mode="json", exclude_unset=True
        )
    if isinstance(request, LayerMoveRequest):
        payload["stack_index"] = request.stack_index
    try:
        invocation = services.invoke_kernel(
            observation, LAYER_MUTATE_HANDLER, payload, request.timeout_seconds
        )
        _reject_target(invocation, "target", request.target)
        evidence = _mutation_evidence(invocation)
        _validate_mutation_evidence(request, evidence, invocation)
        identity_issue = source_target_identity_issue(
            services.target_files, source_file, target_file, request.in_place
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
            staged_file, target_file, overwrite=request.overwrite
        )
        fields = {
            **evidence.model_dump(mode="json"),
            "target_commit": TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
        }
        result_types = {
            "set": LayerSetResult,
            "move": LayerMoveResult,
            "remove": LayerRemoveResult,
            "merge": LayerMergeResult,
        }
        return result_types[operation].model_validate(fields)
    finally:
        services.target_files.discard(staged_file)


def set_layer(request: LayerSetRequest, services: OperationServices) -> LayerSetResult:
    result = _mutate_layer(request, services, "set")
    assert isinstance(result, LayerSetResult)
    return result


def move_layer(
    request: LayerMoveRequest, services: OperationServices
) -> LayerMoveResult:
    result = _mutate_layer(request, services, "move")
    assert isinstance(result, LayerMoveResult)
    return result


def remove_layer(
    request: LayerRemoveRequest, services: OperationServices
) -> LayerRemoveResult:
    result = _mutate_layer(request, services, "remove")
    assert isinstance(result, LayerRemoveResult)
    return result


def merge_layer(
    request: LayerMergeRequest, services: OperationServices
) -> LayerMergeResult:
    result = _mutate_layer(request, services, "merge")
    assert isinstance(result, LayerMergeResult)
    return result


LAYER_OPERATIONS = (
    OperationDescriptor(
        "layer list",
        LayerListRequest,
        LayerListResult,
        list_layers,
        lambda result: f"{result.sprite_file}: {len(result.layers)} root Layers",
        LAYER_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
    OperationDescriptor(
        "layer get",
        LayerGetRequest,
        LayerGetResult,
        get_layer,
        lambda result: (
            f"{result.sprite_file}: {result.layer.name} at {result.layer.path}"
        ),
        LAYER_REQUIREMENTS,
        LAYER_GET_FAILURE_CODES,
    ),
    OperationDescriptor(
        "layer add",
        LayerAddRequest,
        LayerAddResult,
        add_layer,
        lambda result: (
            f"{result.target_commit.target_sprite_file}: {result.layer.name} at {result.layer.path}"
        ),
        LAYER_REQUIREMENTS,
        LAYER_ADD_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "layer set",
        LayerSetRequest,
        LayerSetResult,
        set_layer,
        lambda result: result.target_commit.target_sprite_file,
        LAYER_MUTATION_REQUIREMENTS,
        LAYER_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "layer move",
        LayerMoveRequest,
        LayerMoveResult,
        move_layer,
        lambda result: result.target_commit.target_sprite_file,
        LAYER_MUTATION_REQUIREMENTS,
        LAYER_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "layer remove",
        LayerRemoveRequest,
        LayerRemoveResult,
        remove_layer,
        lambda result: result.target_commit.target_sprite_file,
        LAYER_MUTATION_REQUIREMENTS,
        LAYER_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "layer merge",
        LayerMergeRequest,
        LayerMergeResult,
        merge_layer,
        lambda result: result.target_commit.target_sprite_file,
        LAYER_MERGE_REQUIREMENTS,
        LAYER_MUTATION_FAILURE_CODES,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
