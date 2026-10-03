"""Exact Cel existence, inspection, and lifecycle operations."""

from pathlib import Path
from typing import Literal

from pydantic import (
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.document.cel_contracts import (
    CEL_SUPPORT_RESOURCE,
    CelAddress,
    CelState,
    raise_cel_rejection,
)
from spa.authoring.document.layer import (
    LAYER_ADDRESS_FAILURE_CODES,
    LayerAddress,
)
from spa.authoring.document.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteGetRequest,
    SpriteInspection,
    SpriteMetadata,
    validated_scope,
)
from spa.authoring.raster.image_snapshot import SNAPSHOT_RESOURCE
from spa.authoring.tile.cel_add import (
    TILE_CEL_RESOURCE,
    TilemapCreationEvidence,
    TilemapSize,
    require_tilemap_creation,
)
from spa.authoring.tile.inspection import TILE_INSPECTION_RESOURCE
from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
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
)
from spa.contracts.raster import RASTER_COLOR_RESOURCE, ColorValue, Point, Rectangle


class CelListRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)
    layer: LayerAddress
    from_frame: int = Field(ge=1, strict=True)
    to_frame: int = Field(ge=1, strict=True)

    _validate_sprite = field_validator("sprite_file")(validate_native_sprite_path)

    @model_validator(mode="after")
    def validate_range(self) -> "CelListRequest":
        if self.from_frame > self.to_frame:
            raise ValueError("Frame Range must be ordered")
        return self


class CelGetRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)
    target: CelAddress

    _validate_sprite = field_validator("sprite_file")(validate_native_sprite_path)


class CelListResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa cel list"] = "spa cel list"
    sprite_file: str
    cels: list[CelState]


class CelGetResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa cel get"] = "spa cel get"
    sprite_file: str
    cel: CelState


class CelTargetInput(PublicModel):
    target: CelAddress


class CelImageSize(PublicModel):
    width: int = Field(ge=1, le=65535, strict=True)
    height: int = Field(ge=1, le=65535, strict=True)


class CelAddInput(CelTargetInput):
    model_config = ConfigDict(
        json_schema_extra={
            "not": {
                "required": ["image_size", "tilemap_size"],
                "properties": {
                    "image_size": {"type": "object"},
                    "tilemap_size": {"type": "object"},
                },
            },
        }
    )
    image_size: CelImageSize | None = None
    tilemap_size: TilemapSize | None = Field(
        default=None,
        description="Required for Tilemap Layers: explicit width and height in Tile Cells. "
        "Mutually exclusive with raster image_size; requires aseprite_tile_cel_creation.",
    )

    @model_validator(mode="after")
    def one_geometry(self) -> "CelAddInput":
        if self.image_size is not None and self.tilemap_size is not None:
            raise ValueError("image_size and tilemap_size are mutually exclusive")
        return self


class CelMutationRequest(RuntimeRequest, CelTargetInput):
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
    def validate_commit_intent(self) -> "CelMutationRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class CelAddRequest(CelMutationRequest, CelAddInput):
    pass


class CelClearRequest(CelMutationRequest):
    background_color: ColorValue | None = None


class CelRemoveRequest(CelMutationRequest):
    pass


def validate_added_cel(
    request: CelAddInput,
    cel: CelState,
    canvas: SpriteMetadata,
    invocation: KernelInvocationResult,
    tilemap_creation: TilemapCreationEvidence | None = None,
) -> None:
    """Check initial Image facts, before later Plan Steps can change the Cel."""
    size = request.image_size
    expected = Rectangle(
        x=0,
        y=0,
        width=size.width if size is not None else canvas.width,
        height=size.height if size is not None else canvas.height,
    )
    geometry_matches = (
        cel.is_tilemap
        and cel.image_bounds is None
        and tilemap_creation is not None
        and tilemap_creation.matches(request.tilemap_size, cel)
        if request.tilemap_size is not None
        else not cel.is_tilemap
        and tilemap_creation is None
        and cel.image_bounds == expected
    )
    if (
        not cel.exists
        or cel.content != "transparent"
        or cel.is_background
        or not geometry_matches
        or cel.position != Point(x=0, y=0)
        or cel.opacity != 255
        or cel.z_index != 0
        or cel.linked_cels
    ):
        raise RuntimeIssue(
            "postcondition_failed",
            "Added Cel Image differs from its requested initial state",
            PostconditionEvidence(
                response_path=invocation.response_path,
                reason="Cel Image size, placement, transparency, or independence disagrees",
            ),
            invocation.diagnostics,
        )


class CelMutationEvidence(PublicModel):
    before: CelState
    before_cel_count: int = Field(ge=0)
    cel: CelState
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]


class CelAddEvidence(CelMutationEvidence):
    tilemap_creation: TilemapCreationEvidence | None = None


class CelAddResult(CelAddEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa cel add"] = "spa cel add"
    target_commit: TargetCommit


class CelClearResult(CelMutationEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa cel clear"] = "spa cel clear"
    affected_cels: list[CelState] = Field(min_length=1)
    target_commit: TargetCommit


class CelRemoveResult(CelMutationEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa cel remove"] = "spa cel remove"
    target_commit: TargetCommit


CEL_READ_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_cel_lifecycle"],
)
CEL_SELECT_RESOURCE = PackagedResource(
    "layer_select", "document/layer/layer_select.lua"
)
CEL_GET_HANDLER = PackagedHandler(
    "cel_get",
    "document/cel/cel_get.lua",
    (*SPRITE_INSPECTION_RESOURCES, CEL_SUPPORT_RESOURCE),
)
CEL_MUTATION_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_cel_lifecycle"],
)
CEL_MUTATE_HANDLER = PackagedHandler(
    "cel_mutate",
    "document/cel/cel_mutate.lua",
    (
        *SPRITE_INSPECTION_RESOURCES,
        SPRITE_PERSISTENCE_RESOURCE,
        CEL_SUPPORT_RESOURCE,
        PackagedResource("frame", "document/frame/frame_support.lua"),
        EFFECTIVE_PALETTE_RESOURCE,
        DIGEST_RESOURCE,
        TILE_CEL_RESOURCE,
        TILE_INSPECTION_RESOURCE,
        PackagedResource("tile_properties", "tile/properties.lua"),
        SNAPSHOT_RESOURCE,
        RASTER_COLOR_RESOURCE,
    ),
)


def list_cels(request: CelListRequest, services: OperationServices) -> CelListResult:
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        CEL_GET_HANDLER,
        {
            "operation": "list",
            "sprite_file": request.sprite_file,
            "layer": request.layer.model_dump(exclude_none=True),
            "from_frame": request.from_frame,
            "to_frame": request.to_frame,
        },
        request.timeout_seconds,
    )
    raise_cel_rejection(
        invocation, request.layer, None, (request.from_frame, request.to_frame)
    )
    try:
        cels = [CelState.model_validate(item) for item in invocation.payload["cels"]]
        selected_path = invocation.payload["selected_path"]
        if (
            len(cels) != request.to_frame - request.from_frame + 1
            or any(
                cel.frame_number != number or cel.layer_path != selected_path
                for number, cel in enumerate(cels, request.from_frame)
            )
            or (
                request.layer.layer_path is not None
                and selected_path != request.layer.layer_path
            )
        ):
            raise ValueError("Cel list differs from the resolved Layer and Frame Range")
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            f"Packaged Cel handler returned invalid Cel facts: {exc}",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc
    return CelListResult(sprite_file=request.sprite_file, cels=cels)


def get_cel(request: CelGetRequest, services: OperationServices) -> CelGetResult:
    observation = services.probe_runtime(request)
    invocation = services.invoke_kernel(
        observation,
        CEL_GET_HANDLER,
        {
            "operation": "get",
            "sprite_file": request.sprite_file,
            "target": request.target.model_dump(exclude_none=True),
        },
        request.timeout_seconds,
    )
    raise_cel_rejection(
        invocation,
        request.target.layer,
        request.target,
        (request.target.frame_number, request.target.frame_number),
    )
    try:
        cel = CelState.model_validate(invocation.payload["cel"])
        if cel.frame_number != request.target.frame_number or (
            request.target.layer.layer_path is not None
            and cel.layer_path != request.target.layer.layer_path
        ):
            raise ValueError("Cel Get differs from target address")
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Packaged Cel handler returned invalid Cel facts",
            ResponseEvidence(response_path=invocation.response_path),
            invocation.diagnostics,
        ) from exc
    return CelGetResult(sprite_file=request.sprite_file, cel=cel)


def _mutate(
    request: CelAddRequest | CelClearRequest | CelRemoveRequest,
    services: OperationServices,
    operation: Literal["add", "clear", "remove"],
) -> CelAddResult | CelClearResult | CelRemoveResult:
    source = Path(request.source_sprite_file)
    target_file = Path(request.target_sprite_file)
    identity_issue = source_target_identity_issue(
        services.target_files, source, target_file, request.in_place
    )
    if identity_issue is not None:
        raise RequestIssue([identity_issue])
    observation = services.probe_runtime(request)
    if isinstance(request, CelAddRequest) and request.tilemap_size is not None:
        require_tilemap_creation(observation)
    staged = services.target_files.staged_path(target_file)
    payload: dict[str, object] = {
        "operation": operation,
        "source_sprite_file": request.source_sprite_file,
        "staged_sprite_file": str(staged),
        "target": request.target.model_dump(mode="json", exclude_none=True),
    }
    if isinstance(request, CelAddRequest) and request.image_size is not None:
        payload["image_size"] = request.image_size.model_dump(mode="json")
    if isinstance(request, CelAddRequest) and request.tilemap_size is not None:
        payload["tilemap_size"] = request.tilemap_size.model_dump(mode="json")
    if isinstance(request, CelClearRequest) and request.background_color is not None:
        payload["background_color"] = request.background_color.model_dump(mode="json")
    try:
        invocation = services.invoke_kernel(
            observation, CEL_MUTATE_HANDLER, payload, request.timeout_seconds
        )
        number = request.target.frame_number
        raise_cel_rejection(
            invocation, request.target.layer, request.target, (number, number)
        )
        try:
            mutation_payload = dict(invocation.payload)
            raw_affected = mutation_payload.pop("affected_cels", None)
            evidence_type = (
                CelAddEvidence if operation == "add" else CelMutationEvidence
            )
            evidence = evidence_type.model_validate(mutation_payload)
            if operation == "clear" and not isinstance(raw_affected, list):
                raise TypeError("Cel clear did not report affected Cels")
            affected_cels = (
                [CelState.model_validate(item) for item in raw_affected]
                if operation == "clear"
                else []
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Packaged Cel handler returned invalid mutation evidence: {exc}",
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
        expected_count = (
            evidence.before_cel_count + {"add": 1, "clear": 0, "remove": -1}[operation]
        )
        matching = [
            cel
            for cel in evidence.sprite.cels or []
            if cel.layer_path == evidence.cel.layer_path and cel.frame_number == number
        ]
        expected_affected = {
            (tuple(evidence.cel.layer_path), evidence.cel.frame_number)
        } | {
            (tuple(link.layer_path), link.frame_number)
            for link in evidence.before.linked_cels
        }
        observed_affected = [
            (tuple(cel.layer_path), cel.frame_number) for cel in affected_cels
        ]
        expected_bounds = evidence.cel.image_bounds
        if (
            isinstance(evidence, CelAddEvidence)
            and evidence.tilemap_creation is not None
        ):
            coverage = evidence.tilemap_creation.tilemap.canvas_coverage
            expected_bounds = (
                Rectangle.model_validate(coverage.model_dump()) if coverage else None
            )
        if (
            evidence.cel.frame_number != number
            or evidence.before.frame_number != number
            or evidence.cel.layer_path != evidence.before.layer_path
            or (
                request.target.layer.layer_path is not None
                and evidence.cel.layer_path != request.target.layer.layer_path
            )
            or evidence.sprite.metadata.cel_count != expected_count
            or evidence.before.exists != (operation != "add")
            or evidence.cel.exists != (operation != "remove")
            or len(matching) != (0 if operation == "remove" else 1)
            or (matching and matching[0].bounds != expected_bounds)
            or (
                operation == "clear"
                and not evidence.cel.is_background
                and evidence.cel.content != "transparent"
            )
            or (
                operation == "clear"
                and (
                    len(observed_affected) != len(expected_affected)
                    or set(observed_affected) != expected_affected
                    or evidence.cel not in affected_cels
                    or evidence.cel.linked_cels != evidence.before.linked_cels
                    or any(
                        not cel.exists
                        or cel.content != evidence.cel.content
                        or cel.is_background != evidence.cel.is_background
                        or len(
                            [
                                item
                                for item in evidence.sprite.cels or []
                                if item.layer_path == cel.layer_path
                                and item.frame_number == cel.frame_number
                                and item.bounds == cel.image_bounds
                            ]
                        )
                        != 1
                        for cel in affected_cels
                    )
                )
            )
        ):
            raise RuntimeIssue(
                "postcondition_failed",
                "Persisted Cel evidence differs from the request",
                PostconditionEvidence(
                    response_path=invocation.response_path,
                    reason="Cel existence, content, or count disagrees",
                ),
                invocation.diagnostics,
            )
        if isinstance(request, CelAddRequest):
            assert isinstance(evidence, CelAddEvidence)
            validate_added_cel(
                request,
                evidence.cel,
                evidence.sprite.metadata,
                invocation,
                evidence.tilemap_creation,
            )
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
        if operation == "add":
            return CelAddResult.model_validate(fields)
        if operation == "clear":
            fields["affected_cels"] = affected_cels
            return CelClearResult.model_validate(fields)
        return CelRemoveResult.model_validate(fields)
    finally:
        services.target_files.discard(staged)


def add_cel(request: CelAddRequest, services: OperationServices) -> CelAddResult:
    result = _mutate(request, services, "add")
    assert isinstance(result, CelAddResult)
    return result


def clear_cel(request: CelClearRequest, services: OperationServices) -> CelClearResult:
    result = _mutate(request, services, "clear")
    assert isinstance(result, CelClearResult)
    return result


def remove_cel(
    request: CelRemoveRequest, services: OperationServices
) -> CelRemoveResult:
    result = _mutate(request, services, "remove")
    assert isinstance(result, CelRemoveResult)
    return result


CEL_OPERATIONS = (
    OperationDescriptor(
        "cel list",
        CelListRequest,
        CelListResult,
        list_cels,
        lambda result: f"{len(result.cels)} Cel intersections",
        CEL_READ_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            *LAYER_ADDRESS_FAILURE_CODES,
            "cel_frame_out_of_bounds",
        ),
    ),
    OperationDescriptor(
        "cel get",
        CelGetRequest,
        CelGetResult,
        get_cel,
        lambda result: "Cel exists" if result.cel.exists else "Cel absent",
        CEL_READ_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            *LAYER_ADDRESS_FAILURE_CODES,
            "cel_frame_out_of_bounds",
        ),
    ),
    OperationDescriptor(
        "cel add",
        CelAddRequest,
        CelAddResult,
        add_cel,
        lambda result: result.target_commit.target_sprite_file,
        CEL_MUTATION_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            *LAYER_ADDRESS_FAILURE_CODES,
            "cel_frame_out_of_bounds",
            "cel_unsupported_target",
            "cel_already_exists",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
        plan_eligible=True,
    ),
    OperationDescriptor(
        "cel clear",
        CelClearRequest,
        CelClearResult,
        clear_cel,
        lambda result: result.target_commit.target_sprite_file,
        CEL_MUTATION_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            *LAYER_ADDRESS_FAILURE_CODES,
            "cel_frame_out_of_bounds",
            "cel_unsupported_target",
            "cel_not_found",
            "cel_background_color_required",
            "cel_background_color_incompatible",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "cel remove",
        CelRemoveRequest,
        CelRemoveResult,
        remove_cel,
        lambda result: result.target_commit.target_sprite_file,
        CEL_MUTATION_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            *LAYER_ADDRESS_FAILURE_CODES,
            "cel_frame_out_of_bounds",
            "cel_unsupported_target",
            "cel_not_found",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
