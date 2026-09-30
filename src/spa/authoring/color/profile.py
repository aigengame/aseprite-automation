"""Native Color Profile assignment and conversion, independent of Color Mode."""

from pathlib import Path
from typing import Literal

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
    KernelInvocationResult,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import PublicModel, RuntimeRequest, RuntimeRequirements

PROFILE_FILE_RESOURCE = PackagedResource("color_profile_file", "color/profile_file.lua")
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


class ProfileTarget(PublicModel):
    kind: Literal["none", "srgb"]


class AssignProfileInput(PublicModel):
    profile: ProfileTarget


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
    layer_path: list[int] = Field(min_length=1)
    frame_number: int = Field(ge=1)


class PaletteColorChange(StoredColorChange):
    palette_frame_number: int = Field(ge=1)
    changed_indexes: list[int]


class TileImageChange(StoredColorChange):
    tile_index: int = Field(ge=0)


class TilesetColorChange(PublicModel):
    tileset_index: int = Field(ge=1)
    name: str
    tiles: list[TileImageChange]


class ProfileEvidence(PublicModel):
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


def validate_profile_evidence(
    request: AssignProfileInput,
    evidence: ProfileEvidence,
    invocation: KernelInvocationResult,
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
    if any(item.changed for item in [*evidence.images, *evidence.palettes]) or any(
        tile.changed for tileset in evidence.tilesets for tile in tileset.tiles
    ):
        raise RuntimeIssue(
            "response_malformed",
            "Assign Color Profile changed stored colors",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        )


def assign_profile(
    request: AssignProfileRequest, services: OperationServices
) -> AssignProfileResult:
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
            PROFILE_HANDLER,
            {
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(mutation.staged_sprite_file),
                "operation": "assign",
                "profile": request.profile.model_dump(),
            },
            request.timeout_seconds,
        )
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
        validate_profile_evidence(request, evidence, invocation)
        return AssignProfileResult(
            **evidence.model_dump(), target_commit=mutation.commit()
        )


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
        (*RUNTIME_FAILURE_CODES, "target_commit_failed"),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
