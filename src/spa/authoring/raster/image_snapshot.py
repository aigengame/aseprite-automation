"""Complete Image observation and replacement through canonical Raster values."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.document.cel import (
    CEL_SUPPORT_RESOURCE,
    CelAddress,
    CelFrameRangeDetails,
    CelState,
    raise_cel_rejection,
)
from spa.authoring.document.layer import (
    LAYER_ADDRESS_FAILURE_CODES,
    LAYER_SELECT_RESOURCE,
    LayerAddress,
)
from spa.authoring.document.sprite import (
    INSPECTION_SECTIONS,
    SPRITE_INSPECTION_RESOURCE,
    SPRITE_PERSISTENCE_RESOURCE,
    SpriteGetRequest,
    SpriteInspection,
    validated_scope,
)
from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    source_target_identity_issue,
    validate_native_sprite_path,
)
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
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
from spa.contracts.raster import (
    RASTER_COLOR_RESOURCE,
    ColorValue,
    EffectivePaletteFact,
    ImageContentDigest,
    PixelRegionSnapshot,
    PositiveRectangle,
    Size,
)

INLINE_SNAPSHOT_PIXELS = 4096


class SnapshotDestination(PublicModel):
    path: str = Field(
        min_length=6,
        pattern=r"^[^\x00\r\n]+\.json$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    if_exists: Literal["fail", "replace"]


class SnapshotArtifact(PublicModel):
    role: Literal["pixel-region-snapshot"] = "pixel-region-snapshot"
    media_type: Literal["application/json"] = "application/json"
    format: Literal["json"] = "json"
    path: str
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SnapshotDetails(PublicModel):
    kind: Literal["image_snapshot"] = "image_snapshot"
    reason: str


IMAGE_SNAPSHOT_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "image_composition_unsupported",
        "Native composition cannot preserve the requested output semantics",
        "input",
        SnapshotDetails,
    ),
    FailureCodeSpec(
        "image_snapshot_invalid",
        "Snapshot cannot replace this complete Image",
        "input",
        SnapshotDetails,
    ),
    FailureCodeSpec(
        "image_rectangle_out_of_bounds",
        "Source Rectangle exceeds Image or Canvas bounds",
        "input",
        SnapshotDetails,
    ),
)


class IndividualImageSource(PublicModel):
    kind: Literal["individual"]
    target: CelAddress
    rectangle: PositiveRectangle


class VisibleComposition(PublicModel):
    mode: Literal["visible"]


class IncludeComposition(PublicModel):
    mode: Literal["include"]
    layers: list[LayerAddress] = Field(min_length=1)


LayerComposition = Annotated[
    VisibleComposition | IncludeComposition, Field(discriminator="mode")
]


class CompositeImageSource(PublicModel):
    kind: Literal["composite"]
    output_color_mode: Literal["preserve", "rgb"] = Field(
        description=(
            "Explicit native render destination: preserve uses source Color Mode "
            "and requires an applicable Effective Palette for Indexed output; "
            "rgb produces a derived RGBA observation. No automatic fallback."
        )
    )
    frame_number: int = Field(ge=1)
    rectangle: PositiveRectangle
    layer_composition: LayerComposition


class ImageGetRequest(RuntimeRequest):
    sprite_file: str = Field(min_length=1)
    source: Annotated[
        IndividualImageSource | CompositeImageSource, Field(discriminator="kind")
    ]
    snapshot_destination: SnapshotDestination | None = Field(
        default=None,
        description=(
            "Write the complete canonical Snapshot as a JSON Artifact. Required above "
            "4096 pixels; without it a bounded Snapshot is returned inline."
        ),
    )

    _validate_source = field_validator("sprite_file")(validate_native_sprite_path)

    @model_validator(mode="after")
    def bound_inline_output(self) -> "ImageGetRequest":
        area = self.source.rectangle
        if (
            self.snapshot_destination is None
            and area.width * area.height > INLINE_SNAPSHOT_PIXELS
        ):
            raise ValueError("Snapshots above 4096 pixels require snapshot_destination")
        return self


class IndividualImageFacts(IndividualImageSource):
    coordinate_space: Literal["image-pixel"]
    layer_kind: Literal["transparent", "background", "reference"]
    image_size: Size
    associated_cels: list[CelState] = Field(min_length=1)


class CompositeImageFacts(CompositeImageSource):
    coordinate_space: Literal["canvas-pixel"]
    color_mode: Literal["rgb", "grayscale", "indexed"]
    mask_color: ColorValue
    resolved_layer_paths: list[list[int]]
    compose_groups: Literal[True]
    reference_layers_rendered: Literal[False]


class ImageGetEvidence(PublicModel):
    source: Annotated[
        IndividualImageFacts | CompositeImageFacts, Field(discriminator="kind")
    ]
    snapshot: PixelRegionSnapshot | None
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    color_mode: Literal["rgb", "grayscale", "indexed"]
    mask_color: ColorValue
    effective_palettes: list[EffectivePaletteFact] = Field(
        description=(
            "Indexed Source Palette basis at the requested Frame. Index entries "
            "describe Indexed output only; a derived RGB composite has no "
            "per-pixel Palette Index identity."
        )
    )

    @model_validator(mode="after")
    def validate_composite_mode(self) -> "ImageGetEvidence":
        if isinstance(self.source, CompositeImageFacts):
            expected = (
                self.source.color_mode
                if self.source.output_color_mode == "preserve"
                else "rgb"
            )
            if self.color_mode != expected:
                raise ValueError("Composite output Color Mode contradicts its policy")
        return self


class ImageGetResult(ImageGetEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image get"] = "spa image get"
    sprite_file: str
    output_form: Literal["inline", "artifact"]
    artifact: SnapshotArtifact | None

    @model_validator(mode="after")
    def validate_transport(self) -> "ImageGetResult":
        if (self.snapshot is not None) != (self.output_form == "inline") or (
            self.artifact is not None
        ) != (self.output_form == "artifact"):
            raise ValueError("Snapshot transport contradicts output_form")
        return self


class InlineSnapshot(PublicModel):
    kind: Literal["inline"]
    snapshot: PixelRegionSnapshot

    @model_validator(mode="after")
    def bound_inline_input(self) -> "InlineSnapshot":
        area = self.snapshot.rectangle
        if area.width * area.height > INLINE_SNAPSHOT_PIXELS:
            raise ValueError("Snapshots above 4096 pixels require an Artifact input")
        return self


class ArtifactSnapshot(PublicModel):
    kind: Literal["artifact"]
    path: str = Field(min_length=1)


class ImageReplaceRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool
    target: CelAddress
    input: Annotated[InlineSnapshot | ArtifactSnapshot, Field(discriminator="kind")]

    _validate_source = field_validator("source_sprite_file")(
        validate_native_sprite_path
    )
    _validate_target = field_validator("target_sprite_file")(
        validate_native_sprite_path
    )

    @model_validator(mode="after")
    def validate_intent(self) -> "ImageReplaceRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class ImageReplaceEvidence(PublicModel):
    input_form: Literal["inline", "artifact"]
    target: CelAddress
    color_mode: Literal["rgb", "grayscale", "indexed"]
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    affected_cels: list[CelState] = Field(min_length=1)
    effective_palettes: list[EffectivePaletteFact]
    before_content_digest: ImageContentDigest
    after_content_digest: ImageContentDigest
    geometry_unchanged: Literal[True]
    native_sharing_preserved: Literal[True]
    persisted_reopen_verified: Literal[True]
    sprite: SpriteInspection


class ImageReplaceResult(ImageReplaceEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image replace"] = "spa image replace"
    target_commit: TargetCommit


SNAPSHOT_RESOURCE = PackagedResource(
    "image_snapshot", "raster/image/image_snapshot.lua"
)
COMPOSITION_RESOURCE = PackagedResource(
    "layer_composition", "raster/image/layer_composition.lua"
)
SNAPSHOT_SUPPORT_RESOURCES = (
    SPRITE_INSPECTION_RESOURCE,
    LAYER_SELECT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    SNAPSHOT_RESOURCE,
    RASTER_COLOR_RESOURCE,
    EFFECTIVE_PALETTE_RESOURCE,
)
IMAGE_GET_HANDLER = PackagedHandler(
    "image_get",
    "raster/image/image_get.lua",
    (*SNAPSHOT_SUPPORT_RESOURCES, COMPOSITION_RESOURCE),
)
IMAGE_SNAPSHOT_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=[
        "aseprite_image_snapshot",
        "aseprite_cel_lifecycle",
        "aseprite_sprite_inspection",
    ],
)
IMAGE_REPLACE_HANDLER = PackagedHandler(
    "image_replace",
    "raster/image/image_replace.lua",
    (
        *SNAPSHOT_SUPPORT_RESOURCES,
        SPRITE_PERSISTENCE_RESOURCE,
        DIGEST_RESOURCE,
    ),
)


def _reject_snapshot(invocation) -> None:
    rejected = invocation.payload.get("rejection")
    if (
        isinstance(rejected, dict)
        and isinstance(rejected.get("code"), str)
        and rejected["code"]
        in {spec.code for spec in IMAGE_SNAPSHOT_FAILURE_CODE_SPECS}
        and isinstance(rejected.get("message"), str)
    ):
        raise OperationIssue(
            rejected["code"],
            rejected["message"],
            SnapshotDetails(reason=rejected["message"]),
        )


def _reject_get(
    invocation, source: IndividualImageSource | CompositeImageSource
) -> None:
    _reject_snapshot(invocation)
    if isinstance(source, IndividualImageSource):
        target = source.target
        raise_cel_rejection(
            invocation, target.layer, target, (target.frame_number, target.frame_number)
        )
        return
    rejection = invocation.payload.get("rejection")
    if rejection is None:
        return
    if isinstance(rejection, dict) and isinstance(rejection.get("message"), str):
        if rejection.get("code") == "cel_frame_out_of_bounds":
            raise OperationIssue(
                "cel_frame_out_of_bounds",
                rejection["message"],
                CelFrameRangeDetails(
                    from_frame=source.frame_number, to_frame=source.frame_number
                ),
            )
        index = rejection.get("selector_number")
        if (
            isinstance(source.layer_composition, IncludeComposition)
            and isinstance(index, int)
            and 1 <= index <= len(source.layer_composition.layers)
        ):
            raise_cel_rejection(
                invocation,
                source.layer_composition.layers[index - 1],
                None,
                (source.frame_number, source.frame_number),
            )
    raise RuntimeIssue(
        "response_malformed",
        "Invalid composition rejection",
        ResponseEvidence(invocation.response_path),
        invocation.diagnostics,
    )


def _source_matches(
    requested: IndividualImageSource | CompositeImageSource,
    actual: IndividualImageFacts | CompositeImageFacts,
) -> bool:
    if requested.kind != actual.kind or requested.rectangle != actual.rectangle:
        return False
    if isinstance(requested, IndividualImageSource) and isinstance(
        actual, IndividualImageFacts
    ):
        return requested.target.frame_number == actual.target.frame_number and (
            requested.target.layer.layer_path is None
            or requested.target.layer.layer_path == actual.target.layer.layer_path
        )
    if isinstance(requested, CompositeImageSource) and isinstance(
        actual, CompositeImageFacts
    ):
        return (
            requested.frame_number == actual.frame_number
            and requested.layer_composition == actual.layer_composition
            and requested.output_color_mode == actual.output_color_mode
        )
    return False


def get_image(request: ImageGetRequest, services: OperationServices) -> ImageGetResult:
    files = services.artifact_files
    destination, staged = None, None
    if request.snapshot_destination is not None:
        assert files is not None
        destination = files.normalize_destination(request.snapshot_destination.path)
        files.ensure_source_separate(Path(request.sprite_file), destination)
        staged = files.staged_path(
            destination, if_exists=request.snapshot_destination.if_exists
        )
    try:
        observation = services.probe_runtime(request)
        payload = {
            "sprite_file": request.sprite_file,
            "source": request.source.model_dump(mode="json", exclude_none=True),
        }
        if staged is not None:
            payload["staged_snapshot_file"] = str(staged)
        invocation = services.invoke_kernel(
            observation, IMAGE_GET_HANDLER, payload, request.timeout_seconds
        )
        _reject_get(invocation, request.source)
        artifact = None
        staged_payload = (
            files.read_staged(staged)
            if staged is not None and files is not None
            else None
        )
        try:
            evidence = ImageGetEvidence.model_validate(invocation.payload)
            value = (
                PixelRegionSnapshot.model_validate_json(staged_payload.payload)
                if staged_payload is not None
                else evidence.snapshot
            )
            if (
                value is None
                or not _source_matches(request.source, evidence.source)
                or evidence.width != value.rectangle.width
                or evidence.height != value.rectangle.height
                or evidence.color_mode != value.color_mode
                or evidence.width != request.source.rectangle.width
                or evidence.height != request.source.rectangle.height
                or ((evidence.snapshot is None) != (staged is not None))
            ):
                raise ValueError("Image Get source or Snapshot differs from request")
        except (ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Invalid Image Get evidence: {exc}",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        if staged is not None:
            assert (
                files is not None
                and destination is not None
                and staged_payload is not None
            )
            assert request.snapshot_destination is not None
            files.ensure_source_separate(Path(request.sprite_file), destination)
            published = files.publish(
                staged,
                destination,
                if_exists=request.snapshot_destination.if_exists,
                sha256=staged_payload.sha256,
            )
            artifact = SnapshotArtifact(
                path=published.path,
                byte_size=published.byte_size,
                sha256=published.sha256,
            )
        return ImageGetResult(
            sprite_file=request.sprite_file,
            **evidence.model_dump(),
            output_form="artifact" if artifact else "inline",
            artifact=artifact,
        )
    finally:
        if staged is not None and files is not None:
            files.discard(staged)


def replace_image(
    request: ImageReplaceRequest, services: OperationServices
) -> ImageReplaceResult:
    source, target = Path(request.source_sprite_file), Path(request.target_sprite_file)
    issue = source_target_identity_issue(
        services.target_files, source, target, request.in_place
    )
    if issue is not None:
        raise RequestIssue([issue])
    if isinstance(request.input, InlineSnapshot):
        value = request.input.snapshot
    else:
        files = services.artifact_files
        assert files is not None
        raw = files.read_input(Path(request.input.path))
        try:
            value = PixelRegionSnapshot.model_validate_json(raw)
        except ValidationError as exc:
            raise OperationIssue(
                "image_snapshot_invalid",
                "Input Artifact is not a canonical Snapshot",
                SnapshotDetails(reason=str(exc)),
            ) from exc
    observation = services.probe_runtime(request)
    staged = services.target_files.staged_path(target)
    try:
        invocation = services.invoke_kernel(
            observation,
            IMAGE_REPLACE_HANDLER,
            {
                "source_sprite_file": str(source),
                "staged_sprite_file": str(staged),
                "target": request.target.model_dump(mode="json", exclude_none=True),
                "input": {
                    "kind": request.input.kind,
                    "snapshot": value.model_dump(mode="json"),
                },
            },
            request.timeout_seconds,
        )
        _reject_snapshot(invocation)
        number = request.target.frame_number
        raise_cel_rejection(
            invocation, request.target.layer, request.target, (number, number)
        )
        try:
            evidence = ImageReplaceEvidence.model_validate(invocation.payload)
            if (
                evidence.input_form != request.input.kind
                or evidence.target.frame_number != number
                or (
                    request.target.layer.layer_path is not None
                    and evidence.target.layer.layer_path
                    != request.target.layer.layer_path
                )
                or evidence.color_mode != value.color_mode
                or (evidence.width, evidence.height)
                != (value.rectangle.width, value.rectangle.height)
                or evidence.color_mode != evidence.sprite.metadata.color_mode
            ):
                raise ValueError("Image Replace evidence differs from request")
        except (ValueError, ValidationError) as exc:
            raise RuntimeIssue(
                "response_malformed",
                f"Invalid Image Replace evidence: {exc}",
                ResponseEvidence(invocation.response_path),
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
        if (
            source_target_identity_issue(
                services.target_files, source, target, request.in_place
            )
            is not None
        ):
            raise RuntimeIssue(
                "target_commit_failed",
                "Source/Target identity changed",
                TargetCommitEvidence(str(target), "source_target_identity_changed"),
            )
        committed = services.target_files.commit(
            staged, target, overwrite=request.overwrite
        )
        return ImageReplaceResult(
            **evidence.model_dump(),
            target_commit=TargetCommit(
                target_sprite_file=committed.target_sprite_file,
                byte_size=committed.byte_size,
                sha256=committed.sha256,
            ),
        )
    finally:
        services.target_files.discard(staged)


IMAGE_SNAPSHOT_OPERATIONS = (
    OperationDescriptor(
        "image get",
        ImageGetRequest,
        ImageGetResult,
        get_image,
        lambda result: f"{result.width} x {result.height}",
        IMAGE_SNAPSHOT_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "cel_not_found",
            "cel_unsupported_target",
            "cel_frame_out_of_bounds",
            *LAYER_ADDRESS_FAILURE_CODES,
            "image_rectangle_out_of_bounds",
            "image_composition_unsupported",
            "artifact_file_failed",
        ),
        side_effects=(
            "publishes a JSON Snapshot only when snapshot_destination is declared",
        ),
    ),
    OperationDescriptor(
        "image replace",
        ImageReplaceRequest,
        ImageReplaceResult,
        replace_image,
        lambda result: result.target_commit.target_sprite_file,
        IMAGE_SNAPSHOT_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "target_commit_failed",
            "cel_not_found",
            "cel_unsupported_target",
            "cel_frame_out_of_bounds",
            *LAYER_ADDRESS_FAILURE_CODES,
            "image_snapshot_invalid",
            "artifact_file_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
