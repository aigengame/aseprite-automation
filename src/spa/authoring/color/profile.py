"""Native Color Profile assignment and conversion, independent of Color Mode."""

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.document.sprite import (
    SPRITE_INSPECTION_RESOURCES,
    SPRITE_PERSISTENCE_RESOURCE,
)
from spa.contracts.digest import DIGEST_RESOURCE
from spa.contracts.mutation import (
    TargetCommit,
    require_overwrite_for_in_place,
    validate_native_sprite_path,
)
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    IccVerificationError,
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

PROFILE_FILE_RESOURCE = PackagedResource("color_profile_file", "color/profile_file.lua")
PROFILE_PROBE_FIXTURE = PackagedResource(
    "profile_fixture", "runtime/fixtures/color_profile_fixture.lua"
)
PROFILE_RESOURCE = PackagedResource("color_profile", "color/profile.lua")
PROFILE_HANDLER = PackagedHandler(
    "color_profile",
    "color/profile_mutation.lua",
    (
        *SPRITE_INSPECTION_RESOURCES,
        SPRITE_PERSISTENCE_RESOURCE,
        DIGEST_RESOURCE,
        PROFILE_RESOURCE,
        PROFILE_FILE_RESOURCE,
    ),
)


class NoneProfile(PublicModel):
    kind: Literal["none"]


class SrgbProfile(PublicModel):
    kind: Literal["srgb"]


class IccProfile(PublicModel):
    kind: Literal["icc"]
    icc_file: str = Field(min_length=1)


class AssignProfileInput(PublicModel):
    profile: Annotated[
        NoneProfile | SrgbProfile | IccProfile, Field(discriminator="kind")
    ]


class ConvertProfileInput(PublicModel):
    profile: Annotated[SrgbProfile | IccProfile, Field(discriminator="kind")]


class ProfileFileDetails(PublicModel):
    kind: Literal["color_profile_file"] = "color_profile_file"
    path: str
    reason: Literal[
        "unreadable", "invalid", "unsupported_color_space", "native_load_failed"
    ]
    step_number: int | None = Field(default=None, ge=1)


class ProfileSourceDetails(PublicModel):
    kind: Literal["color_profile_source"] = "color_profile_source"
    icc_color_space: str
    step_number: int | None = Field(default=None, ge=1)


PROFILE_FAILURE_SPECS = (
    FailureCodeSpec(
        "color_profile_file_failed",
        "The requested ICC file could not be used",
        "input",
        ProfileFileDetails,
    ),
    FailureCodeSpec(
        "color_profile_source_unsupported",
        "Native conversion does not support the current Sprite's ICC color space",
        "input",
        ProfileSourceDetails,
    ),
)


def profile_payload(
    request: AssignProfileInput | ConvertProfileInput,
    services: OperationServices,
    step_number: int | None = None,
) -> dict[str, Any]:
    """Freeze and validate ICC bytes; only the native Kernel applies Color Profiles."""
    result: dict[str, Any] = {"profile": request.profile.model_dump()}
    if not isinstance(request.profile, IccProfile):
        return result
    files = services.artifact_files
    assert files is not None, "ICC file input requires the file adapter"
    path = request.profile.icc_file
    try:
        raw = files.read_input(Path(path))
    except RuntimeIssue as exc:
        raise OperationIssue(
            "color_profile_file_failed",
            "ICC file could not be read",
            ProfileFileDetails(path=path, reason="unreadable", step_number=step_number),
        ) from exc
    verify = services.verify_icc
    assert verify is not None, "ICC input requires the ICC verifier"
    try:
        facts = verify(raw)
    except IccVerificationError as exc:
        raise OperationIssue(
            "color_profile_file_failed",
            "ICC file is invalid",
            ProfileFileDetails(path=path, reason="invalid", step_number=step_number),
        ) from exc
    if isinstance(request, ConvertProfileInput) and facts.color_space != "RGB":
        raise OperationIssue(
            "color_profile_file_failed",
            "Native Color Profile conversion requires an RGB ICC target",
            ProfileFileDetails(
                path=path, reason="unsupported_color_space", step_number=step_number
            ),
        )
    result["icc_bytes"] = raw.hex()
    result["icc_file"] = {
        "path": path,
        "byte_size": facts.byte_size,
        "sha256": facts.sha256,
    }
    return result


def reject_profile(
    invocation: KernelInvocationResult, step_number: int | None = None
) -> None:
    rejected = invocation.payload.get("rejection")
    if rejected is None:
        return
    try:
        code = rejected["code"]
        if code == "color_profile_file_failed":
            details = ProfileFileDetails.model_validate(rejected["details"])
            message = "Native Aseprite could not load the ICC file"
        elif code == "color_profile_source_unsupported":
            details = ProfileSourceDetails.model_validate(rejected["details"])
            message = "Native conversion requires an RGB ICC source profile"
        else:
            raise ValueError("Unknown Color Profile rejection")
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Invalid Color Profile rejection",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc
    raise OperationIssue(
        code,
        message,
        details.model_copy(update={"step_number": step_number}),
    )


class ProfileMutationRequest(RuntimeRequest):
    source_sprite_file: str = Field(min_length=1)
    target_sprite_file: str = Field(min_length=1)
    in_place: bool
    overwrite: bool

    _source = field_validator("source_sprite_file")(validate_native_sprite_path)
    _target = field_validator("target_sprite_file")(validate_native_sprite_path)

    @model_validator(mode="after")
    def validate_intent(self) -> "ProfileMutationRequest":
        require_overwrite_for_in_place(self.in_place, self.overwrite)
        return self


class AssignProfileRequest(ProfileMutationRequest, AssignProfileInput):
    pass


class ConvertProfileRequest(ProfileMutationRequest, ConvertProfileInput):
    pass


class ProfileFacts(PublicModel):
    kind: Literal["none", "srgb", "icc"]
    name: str


class StoredColorChange(PublicModel):
    before_digest: str = Field(pattern=r"^[0-9a-f]{16}$")
    after_digest: str = Field(pattern=r"^[0-9a-f]{16}$")
    changed: bool

    @model_validator(mode="after")
    def validate_change(self) -> "StoredColorChange":
        if self.changed != (self.before_digest != self.after_digest):
            raise ValueError("Stored color change differs from observed digests")
        return self


class CelImageChange(StoredColorChange):
    layer_path: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)
    frame_number: int = Field(ge=1)


class PaletteColorChange(StoredColorChange):
    palette_frame_number: int = Field(ge=1)
    changed_indexes: list[Annotated[int, Field(ge=0)]]

    @model_validator(mode="after")
    def validate_indexes(self) -> "PaletteColorChange":
        if self.changed != bool(self.changed_indexes) or self.changed_indexes != sorted(
            set(self.changed_indexes)
        ):
            raise ValueError(
                "Changed Palette indexes must agree with the stored color change"
            )
        return self


class TileImageChange(StoredColorChange):
    tile_index: int = Field(ge=0)


class TilesetColorChange(PublicModel):
    tileset_index: int = Field(ge=1)
    name: str
    tiles: list[TileImageChange]


class IccFileFacts(PublicModel):
    path: str
    byte_size: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    native_name: str
    matches_effective_profile: Literal[True]


class ProfileEvidence(PublicModel):
    icc_file: IccFileFacts | None
    source_profile: ProfileFacts
    requested_profile: ProfileFacts
    effective_profile: ProfileFacts
    matches_requested_profile: Literal[True]
    profile_changed: bool
    images: list[CelImageChange]
    palettes: list[PaletteColorChange]
    tilesets: list[TilesetColorChange]
    persisted_reopen_verified: bool


class AssignProfileResult(ProfileEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite assign-color-profile"] = (
        "spa sprite assign-color-profile"
    )
    persisted_reopen_verified: Literal[True]
    target_commit: TargetCommit


class ConvertProfileResult(ProfileEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa sprite convert-color-profile"] = (
        "spa sprite convert-color-profile"
    )
    persisted_reopen_verified: Literal[True]
    target_commit: TargetCommit


def validate_profile_evidence(
    request: AssignProfileInput | ConvertProfileInput,
    evidence: ProfileEvidence,
    invocation: KernelInvocationResult,
    prepared: dict[str, Any],
) -> None:
    if (
        evidence.requested_profile.kind != request.profile.kind
        or evidence.effective_profile.kind != evidence.requested_profile.kind
    ):
        raise RuntimeIssue(
            "response_malformed",
            "Color Profile differs from the request",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        )
    if isinstance(request.profile, IccProfile):
        if (
            evidence.icc_file is None
            or evidence.icc_file.path != request.profile.icc_file
            or evidence.icc_file.native_name != evidence.effective_profile.name
        ):
            raise RuntimeIssue(
                "response_malformed",
                "ICC evidence differs from the request",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            )
        if (
            evidence.icc_file.model_dump(
                exclude={"native_name", "matches_effective_profile"}
            )
            != prepared["icc_file"]
        ):
            raise RuntimeIssue(
                "response_malformed",
                "ICC evidence differs from the frozen input",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            )
    elif evidence.icc_file is not None:
        raise RuntimeIssue(
            "response_malformed",
            "Unexpected ICC file evidence",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        )
    if isinstance(request, AssignProfileInput) and (
        any(item.changed for item in [*evidence.images, *evidence.palettes])
        or any(tile.changed for tileset in evidence.tilesets for tile in tileset.tiles)
    ):
        raise RuntimeIssue(
            "response_malformed",
            "Assign Color Profile changed stored colors",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        )


def _mutate_profile(
    request: AssignProfileRequest | ConvertProfileRequest,
    services: OperationServices,
    operation: Literal["assign", "convert"],
) -> tuple[ProfileEvidence, TargetCommit]:
    completion = prepare_mutation(
        services.target_files,
        Path(request.source_sprite_file),
        Path(request.target_sprite_file),
        in_place=request.in_place,
        overwrite=request.overwrite,
        identity_change_message="Source/Target publication identity changed before Target Commit",
    )
    prepared = profile_payload(request, services)
    observation = services.probe_runtime(request)
    with completion as mutation:
        invocation = services.invoke_kernel(
            observation,
            PROFILE_HANDLER,
            {
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(mutation.staged_sprite_file),
                "operation": operation,
                **prepared,
            },
            request.timeout_seconds,
        )
        reject_profile(invocation)
        try:
            evidence = ProfileEvidence.model_validate(invocation.payload)
            if not evidence.persisted_reopen_verified:
                raise ValueError("Color Profile mutation was not reopened")
        except ValueError as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Invalid Color Profile evidence",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        validate_profile_evidence(request, evidence, invocation, prepared)
        return evidence, mutation.commit()


def assign_profile(
    request: AssignProfileRequest, services: OperationServices
) -> AssignProfileResult:
    evidence, committed = _mutate_profile(request, services, "assign")
    return AssignProfileResult(**evidence.model_dump(), target_commit=committed)


def convert_profile(
    request: ConvertProfileRequest, services: OperationServices
) -> ConvertProfileResult:
    evidence, committed = _mutate_profile(request, services, "convert")
    return ConvertProfileResult(**evidence.model_dump(), target_commit=committed)


PROFILE_OPERATIONS = (
    OperationDescriptor(
        "sprite assign-color-profile",
        AssignProfileRequest,
        AssignProfileResult,
        assign_profile,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=[
                "aseprite_sprite_inspection",
                "aseprite_assign_color_profile",
            ],
        ),
        (*RUNTIME_FAILURE_CODES, "color_profile_file_failed", "target_commit_failed"),
        plan_eligible=True,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
    OperationDescriptor(
        "sprite convert-color-profile",
        ConvertProfileRequest,
        ConvertProfileResult,
        convert_profile,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=[
                "aseprite_sprite_inspection",
                "aseprite_convert_color_profile",
            ],
        ),
        (
            *RUNTIME_FAILURE_CODES,
            "color_profile_file_failed",
            "color_profile_source_unsupported",
            "target_commit_failed",
        ),
        plan_eligible=True,
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
