"""Complete Slice snapshots and bounded native Slice authoring."""

from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.document.sprite import (
    SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    SliceFacts,
    SliceKeyFacts,
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
from spa.contracts.raster import Point, PositiveRectangle, RgbaColor


def _native_text(value: str | None) -> str | None:
    if value is not None and "\x00" in value:
        raise ValueError("Slice text cannot contain NUL")
    return value


class SliceAddress(PublicModel):
    """One current-snapshot index or exactly one matching name; no persistent ID."""

    slice_index: int | None = Field(default=None, ge=1)
    slice_name: str | None = None

    _name = field_validator("slice_name")(_native_text)

    @model_validator(mode="after")
    def exactly_one(self) -> "SliceAddress":
        if (self.slice_index is None) == (self.slice_name is None):
            raise ValueError("Specify exactly one Slice address")
        return self


class SliceTargetDetails(PublicModel):
    kind: Literal["slice_target"] = "slice_target"
    address: SliceAddress


SLICE_FAILURE_SPECS = (
    FailureCodeSpec(
        "slice_missing", "No Slice matches the address", "input", SliceTargetDetails
    ),
    FailureCodeSpec(
        "slice_ambiguous",
        "More than one Slice matches the name",
        "input",
        SliceTargetDetails,
    ),
    FailureCodeSpec(
        "slice_geometry_unsupported",
        "Geometry changes require exactly one explicit Slice Key at Frame 1",
        "input",
        SliceTargetDetails,
    ),
)


class SliceKeyFrameRange(PublicModel):
    from_frame: int = Field(ge=1)
    to_frame: int = Field(ge=1)


class EffectiveSliceKeyFacts(SliceKeyFacts):
    effective_frame_range: SliceKeyFrameRange


class IndexedSliceFacts(SliceFacts):
    slice_index: int = Field(ge=1)
    keys: list[EffectiveSliceKeyFacts]


class SliceSnapshot(PublicModel):
    frame_count: int = Field(ge=1)
    slices: list[IndexedSliceFacts]

    @model_validator(mode="after")
    def coherent_snapshot(self) -> "SliceSnapshot":
        for index, item in enumerate(self.slices, 1):
            if item.slice_index != index:
                raise ValueError(
                    "Slice indexes must describe the complete current snapshot"
                )
            previous = 0
            for position, key in enumerate(item.keys):
                end = (
                    item.keys[position + 1].frame_number - 1
                    if position + 1 < len(item.keys)
                    else self.frame_count
                )
                if (
                    not previous < key.frame_number <= self.frame_count
                    or key.effective_frame_range.from_frame != key.frame_number
                    or key.effective_frame_range.to_frame != end
                ):
                    raise ValueError("Slice Keys and effective Frame Ranges disagree")
                previous = key.frame_number
        return self


class SliceListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)

    _sprite = field_validator("sprite_file")(validate_native_sprite_path)


class SliceGetRequest(SliceListRequest):
    target: SliceAddress


class _SliceMutationRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool

    _source = field_validator("source_sprite_file")(validate_native_sprite_path)
    _target = field_validator("target_sprite_file")(validate_native_sprite_path)

    @model_validator(mode="after")
    def commit_intent(self) -> "_SliceMutationRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class SliceAddRequest(_SliceMutationRequest):
    name: str
    data: str = ""
    color: RgbaColor | None = None
    bounds: PositiveRectangle = Field(description="Bounds in Canvas Pixel space.")
    center: PositiveRectangle | None = Field(
        default=None, description="Center relative to the bounds top-left."
    )
    pivot: Point | None = Field(
        default=None, description="Pivot relative to the bounds top-left."
    )

    _text = field_validator("name", "data")(_native_text)


class SliceSetProperties(PublicModel):
    name: str | None = None
    data: str | None = None
    color: RgbaColor | None = None
    bounds: PositiveRectangle | None = Field(
        default=None, description="Bounds in Canvas Pixel space."
    )
    center: PositiveRectangle | None = Field(
        default=None,
        description="Center relative to bounds top-left; null clears the center.",
    )
    pivot: Point | None = Field(
        default=None,
        description="Pivot relative to bounds top-left; omit to preserve. Clearing is unavailable.",
    )

    _text = field_validator("name", "data")(_native_text)

    @model_validator(mode="after")
    def valid_patch(self) -> "SliceSetProperties":
        if not self.model_fields_set:
            raise ValueError("Set requires at least one Slice property")
        if any(
            getattr(self, field) is None for field in self.model_fields_set - {"center"}
        ):
            raise ValueError(
                "Only center can be null; omit other properties to preserve them"
            )
        return self


class SliceSetRequest(_SliceMutationRequest):
    target: SliceAddress
    properties: SliceSetProperties


class SliceRemoveRequest(_SliceMutationRequest):
    target: SliceAddress


class SliceListResult(SliceSnapshot):
    status: Literal["success"] = "success"
    operation: Literal["spa slice list"] = "spa slice list"
    sprite_file: str
    coordinate_space: Literal["canvas-pixel"] = "canvas-pixel"


class SliceGetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa slice get"] = "spa slice get"
    sprite_file: str
    frame_count: int = Field(ge=1)
    coordinate_space: Literal["canvas-pixel"] = "canvas-pixel"
    slice: IndexedSliceFacts


class _SliceMutationResult(SliceSnapshot):
    status: Literal["success"] = "success"
    coordinate_space: Literal["canvas-pixel"] = "canvas-pixel"
    target_commit: TargetCommit
    persisted_reopen_verified: Literal[True]


class SliceAddResult(_SliceMutationResult):
    operation: Literal["spa slice add"] = "spa slice add"


class SliceSetResult(_SliceMutationResult):
    operation: Literal["spa slice set"] = "spa slice set"
    previous_slice: IndexedSliceFacts = Field(
        description="Address and facts in the Source snapshot."
    )


class SliceRemoveResult(_SliceMutationResult):
    operation: Literal["spa slice remove"] = "spa slice remove"
    previous_slice: IndexedSliceFacts = Field(
        description="Removed Slice in the Source snapshot."
    )


SLICE_RESOURCE = PackagedResource("slice", "document/slice/slice_support.lua")
SLICE_READ_HANDLER = PackagedHandler(
    "slice_read",
    "document/slice/slice_read.lua",
    (*SPRITE_INSPECTION_RESOURCES, SLICE_RESOURCE),
)
SLICE_MUTATE_HANDLER = PackagedHandler(
    "slice_mutate",
    "document/slice/slice_mutate.lua",
    (
        *SPRITE_INSPECTION_RESOURCES,
        SPRITE_PERSISTENCE_RESOURCE,
        DIGEST_RESOURCE,
        SLICE_RESOURCE,
    ),
)
SLICE_READ_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection"],
)
SLICE_MUTATION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_sprite_inspection", "aseprite_slice_authoring"],
)


def _malformed(invocation: KernelInvocationResult) -> RuntimeIssue:
    return RuntimeIssue(
        "response_malformed",
        "Packaged Slice handler returned inconsistent evidence",
        ResponseEvidence(response_path=invocation.response_path),
        invocation.diagnostics,
    )


def _reject(invocation: KernelInvocationResult, target: SliceAddress | None) -> None:
    rejection = invocation.payload.get("rejection")
    if rejection is None:
        return
    if (
        isinstance(rejection, dict)
        and rejection.get("code") in tuple(spec.code for spec in SLICE_FAILURE_SPECS)
        and isinstance(rejection.get("message"), str)
        and target is not None
    ):
        raise OperationIssue(
            rejection["code"], rejection["message"], SliceTargetDetails(address=target)
        )
    raise _malformed(invocation)


def _read(
    request: SliceListRequest, services: OperationServices
) -> tuple[SliceSnapshot, IndexedSliceFacts | None]:
    target = request.target if isinstance(request, SliceGetRequest) else None
    invocation = services.invoke_kernel(
        services.probe_runtime(request),
        SLICE_READ_HANDLER,
        {
            "sprite_file": request.sprite_file,
            "target": target.model_dump(exclude_none=True) if target else None,
        },
        request.timeout_seconds,
    )
    _reject(invocation, target)
    try:
        snapshot = SliceSnapshot.model_validate(invocation.payload["snapshot"])
        selected = None
        if target is not None:
            selected = _selected(snapshot, invocation.payload["selected_index"], target)
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise _malformed(invocation) from exc
    return snapshot, selected


def _selected(
    snapshot: SliceSnapshot, index: object, target: SliceAddress
) -> IndexedSliceFacts:
    if type(index) is not int or not 1 <= index <= len(snapshot.slices):
        raise ValueError("invalid selected Slice index")
    selected = snapshot.slices[index - 1]
    if target.slice_index is not None and target.slice_index != index:
        raise ValueError("selected Slice differs from requested index")
    if target.slice_name is not None and (
        selected.name != target.slice_name
        or sum(item.name == target.slice_name for item in snapshot.slices) != 1
    ):
        raise ValueError("selected Slice differs from unique requested name")
    return selected


def list_slices(
    request: SliceListRequest, services: OperationServices
) -> SliceListResult:
    snapshot, _ = _read(request, services)
    return SliceListResult(sprite_file=request.sprite_file, **snapshot.model_dump())


def get_slice(request: SliceGetRequest, services: OperationServices) -> SliceGetResult:
    snapshot, selected = _read(request, services)
    assert selected is not None
    return SliceGetResult(
        sprite_file=request.sprite_file,
        frame_count=snapshot.frame_count,
        slice=selected,
    )


def _mutate(
    request: SliceAddRequest | SliceSetRequest | SliceRemoveRequest,
    services: OperationServices,
) -> SliceAddResult | SliceSetResult | SliceRemoveResult:
    operation = (
        "add"
        if isinstance(request, SliceAddRequest)
        else "set"
        if isinstance(request, SliceSetRequest)
        else "remove"
    )
    address = None if isinstance(request, SliceAddRequest) else request.target
    completion = prepare_mutation(
        services.target_files,
        Path(request.source_sprite_file),
        Path(request.target_sprite_file),
        in_place=request.in_place,
        overwrite=request.overwrite,
        identity_change_message="Source/Target publication identity changed before Slice Target Commit",
    )
    observation = services.probe_runtime(request)
    properties = (
        request.model_dump(
            mode="json",
            include={"name", "data", "color", "bounds", "center", "pivot"},
            exclude_none=True,
        )
        if isinstance(request, SliceAddRequest)
        else request.properties.model_dump(mode="json", exclude_unset=True)
        if isinstance(request, SliceSetRequest)
        else {}
    )
    with completion as staged:
        invocation = services.invoke_kernel(
            observation,
            SLICE_MUTATE_HANDLER,
            {
                "operation": operation,
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(staged.staged_sprite_file),
                "properties": properties,
                "target": address.model_dump(exclude_none=True) if address else None,
            },
            request.timeout_seconds,
        )
        _reject(invocation, address)
        try:
            snapshot = SliceSnapshot.model_validate(invocation.payload["snapshot"])
            before = SliceSnapshot.model_validate(invocation.payload["before"])
            previous = None
            if address is not None:
                previous = _selected(
                    before, invocation.payload["selected_before_index"], address
                )
            if (
                invocation.payload["operation"] != operation
                or invocation.payload["persisted_reopen_verified"] is not True
                or snapshot.frame_count != before.frame_count
                or len(snapshot.slices)
                != len(before.slices) + {"add": 1, "set": 0, "remove": -1}[operation]
            ):
                raise ValueError("Slice mutation evidence differs")
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise _malformed(invocation) from exc
        commit = staged.commit()
        if previous is not None:
            if isinstance(request, SliceRemoveRequest):
                return SliceRemoveResult(
                    target_commit=commit,
                    persisted_reopen_verified=True,
                    previous_slice=previous,
                    **snapshot.model_dump(),
                )
            return SliceSetResult(
                target_commit=commit,
                persisted_reopen_verified=True,
                previous_slice=previous,
                **snapshot.model_dump(),
            )
        return SliceAddResult(
            target_commit=commit,
            persisted_reopen_verified=True,
            **snapshot.model_dump(),
        )


def add_slice(request: SliceAddRequest, services: OperationServices) -> SliceAddResult:
    result = _mutate(request, services)
    assert isinstance(result, SliceAddResult)
    return result


def set_slice(request: SliceSetRequest, services: OperationServices) -> SliceSetResult:
    result = _mutate(request, services)
    assert isinstance(result, SliceSetResult)
    return result


def remove_slice(
    request: SliceRemoveRequest, services: OperationServices
) -> SliceRemoveResult:
    result = _mutate(request, services)
    assert isinstance(result, SliceRemoveResult)
    return result


def slice_capability_gaps(version: str) -> list[CapabilityGap]:
    return [
        CapabilityGap(
            capability="spa slice key add/set/remove",
            aseprite_version=version,
            evidence="No installed arbitrary Slice Key mutation descriptors. The 1.3.18.5 public Lua getters expose the first Key and setters target native Frame 0. A public non-interactive multi-Key save/reopen path needs acceptance before extending this surface (issue #40).",
        ),
        CapabilityGap(
            capability="spa slice set: multi-Key or later-starting geometry",
            aseprite_version=version,
            evidence="Bounds, center, and pivot changes require exactly one explicit Key at Frame 1. Rename, user data, and whole-Slice removal preserve complete Keys.",
        ),
        CapabilityGap(
            capability="spa slice set: clearing pivot",
            aseprite_version=version,
            evidence="Public Lua pivot=nil stores Point(0,0) on 1.3.18.5; clearing is not exposed. Omit pivot to preserve it. A later native clearing path needs save/reopen acceptance.",
        ),
    ]


SLICE_OPERATIONS = (
    OperationDescriptor(
        "slice list",
        SliceListRequest,
        SliceListResult,
        list_slices,
        lambda result: f"{len(result.slices)} Slices",
        SLICE_READ_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
    OperationDescriptor(
        "slice get",
        SliceGetRequest,
        SliceGetResult,
        get_slice,
        lambda result: f"Slice {result.slice.slice_index}: {result.slice.name}",
        SLICE_READ_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "slice_missing", "slice_ambiguous"),
    ),
    OperationDescriptor(
        "slice add",
        SliceAddRequest,
        SliceAddResult,
        add_slice,
        lambda result: result.target_commit.target_sprite_file,
        SLICE_MUTATION_REQUIREMENTS,
        (*RUNTIME_FAILURE_CODES, "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "slice set",
        SliceSetRequest,
        SliceSetResult,
        set_slice,
        lambda result: result.target_commit.target_sprite_file,
        SLICE_MUTATION_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            *(spec.code for spec in SLICE_FAILURE_SPECS),
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "slice remove",
        SliceRemoveRequest,
        SliceRemoveResult,
        remove_slice,
        lambda result: result.target_commit.target_sprite_file,
        SLICE_MUTATION_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "slice_missing",
            "slice_ambiguous",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
