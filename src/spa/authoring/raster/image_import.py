"""Compatible external PNG insertion into an explicitly empty native Cel slot."""

import hashlib
from importlib.resources import files as packaged_files
from pathlib import Path
from typing import Literal, NoReturn

from pydantic import Field, model_validator

from spa.application.mutation import prepare_mutation
from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.color.profile import PROFILE_HANDLER, PROFILE_ICC_RESOURCES
from spa.authoring.document.cel import (
    CEL_SUPPORT_RESOURCE,
    CelMutationRequest,
    CelState,
    raise_cel_rejection,
)
from spa.authoring.document.cel_relationship import CelPosition
from spa.authoring.document.layer import LAYER_ADDRESS_FAILURE_CODES
from spa.authoring.document.sprite import SpriteInspection
from spa.contracts.digest import fnv1a64
from spa.contracts.mutation import TargetCommit
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PngInputError,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequirements
from spa.contracts.raster import EffectivePaletteFact, ImageContentDigest, Rectangle


class ImageImportRequest(CelMutationRequest):
    raster_file: str = Field(min_length=1)
    position: CelPosition


class ImportProfile(PublicModel):
    kind: Literal["none", "srgb", "icc"]
    icc_identity: Literal["linear_srgb", "display_p3"] | None

    @model_validator(mode="after")
    def validate_identity(self) -> "ImportProfile":
        if (self.kind == "icc") != (self.icc_identity is not None):
            raise ValueError("ICC identity must agree with Color Profile kind")
        return self


class RasterInputReceipt(PublicModel):
    path: str
    format: Literal["png"] = "png"
    media_type: Literal["image/png"] = "image/png"
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    color_profile: ImportProfile


class ImportedImage(PublicModel):
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)
    color_mode: Literal["rgb", "indexed"]
    stored_content_digest: ImageContentDigest
    rgba_content_digest: ImageContentDigest


class ImageImportEvidence(PublicModel):
    before: CelState
    before_cel_count: int = Field(ge=0)
    cel: CelState
    image: ImportedImage
    color_profile: ImportProfile
    effective_palette: EffectivePaletteFact | None
    transparent_index: int | None = Field(ge=0, le=255)
    sprite: SpriteInspection
    persisted_reopen_verified: Literal[True]


class ImageImportResult(ImageImportEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa image import"] = "spa image import"
    raster_file: RasterInputReceipt
    target_commit: TargetCommit


ImportRefusal = Literal[
    "unreadable",
    "invalid_png",
    "unsupported_profile",
    "output_alias",
    "color_mode",
    "color_profile",
    "native_load",
    "native_content",
    "palette",
]


class ImageImportDetails(PublicModel):
    kind: Literal["image_import"] = "image_import"
    path: str
    reason: ImportRefusal
    message: str


IMAGE_IMPORT_FAILURE_SPECS = (
    FailureCodeSpec(
        "image_import_incompatible",
        "The PNG cannot be inserted without changing its declared meaning",
        "input",
        ImageImportDetails,
    ),
)
IMAGE_IMPORT_HANDLER = PackagedHandler(
    "image_import",
    "raster/image/image_import.lua",
    (
        *PROFILE_HANDLER.support_resources,
        CEL_SUPPORT_RESOURCE,
        EFFECTIVE_PALETTE_RESOURCE,
    ),
)


def _reject(path: str, reason: ImportRefusal, message: str) -> NoReturn:
    raise OperationIssue(
        "image_import_incompatible",
        message,
        ImageImportDetails(path=path, reason=reason, message=message),
    )


def import_image(
    request: ImageImportRequest, services: OperationServices
) -> ImageImportResult:
    files, decode = services.artifact_files, services.decode_png_input
    assert files is not None and decode is not None, (
        "Image import requires PNG input services"
    )
    path = request.raster_file
    target = Path(request.target_sprite_file)

    def protect_input() -> None:
        if services.target_files.same_publication_target(
            Path(path).expanduser(), target
        ):
            _reject(
                path, "output_alias", "Target Commit would replace the raster input"
            )

    protect_input()
    completion = prepare_mutation(
        services.target_files,
        Path(request.source_sprite_file),
        target,
        in_place=request.in_place,
        overwrite=request.overwrite,
        identity_change_message="Source/Target publication identity changed before Target Commit",
    )
    try:
        raw = files.read_input(Path(path))
    except RuntimeIssue:
        _reject(path, "unreadable", "Cannot read raster input")
    try:
        decoded = decode(raw)
    except PngInputError as exc:
        _reject(path, "invalid_png", str(exc))
    if decoded.width > 65535 or decoded.height > 65535:
        _reject(path, "invalid_png", "PNG exceeds persisted Cel Image dimensions")
    identity = None
    if decoded.icc_bytes is not None:
        for resource in PROFILE_ICC_RESOURCES:
            if (
                packaged_files("spa.kernel")
                .joinpath(resource.package_path)
                .read_bytes()
                == decoded.icc_bytes
            ):
                identity = Path(resource.package_path).stem
                break
        if identity is None:
            _reject(
                path,
                "unsupported_profile",
                "ICC is outside the supported Color Profile set",
            )
    profile = ImportProfile.model_validate(
        {"kind": decoded.color_profile, "icc_identity": identity}
    )
    image = ImportedImage(
        width=decoded.width,
        height=decoded.height,
        color_mode=decoded.color_mode,
        stored_content_digest=ImageContentDigest(value=fnv1a64(decoded.stored_bytes)),
        rgba_content_digest=ImageContentDigest(value=fnv1a64(decoded.rgba_bytes)),
    )
    receipt = RasterInputReceipt(
        path=path,
        byte_size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        color_profile=profile,
    )
    runtime = services.probe_runtime(request)
    with completion as mutation:
        invocation = services.invoke_kernel(
            runtime,
            IMAGE_IMPORT_HANDLER,
            {
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(mutation.staged_sprite_file),
                "target": request.target.model_dump(),
                "position": request.position.model_dump(),
                "raster_path": path,
                "raster_bytes": raw.hex(),
                "decoded": {
                    "width": decoded.width,
                    "height": decoded.height,
                    "color_mode": decoded.color_mode,
                    "stored_bytes": decoded.stored_bytes.hex(),
                    "rgba_bytes": decoded.rgba_bytes.hex(),
                    "profile": profile.model_dump(),
                    "icc_bytes": decoded.icc_bytes.hex()
                    if decoded.icc_bytes is not None
                    else None,
                },
            },
            request.timeout_seconds,
        )
        rejected = invocation.payload.get("rejection")
        if (
            isinstance(rejected, dict)
            and rejected.get("code") == "image_import_incompatible"
        ):
            try:
                details = ImageImportDetails.model_validate(rejected["details"])
                if details.path != path:
                    raise ValueError("Wrong raster input in rejection")
            except (KeyError, ValueError) as exc:
                raise RuntimeIssue(
                    "response_malformed",
                    "Invalid import rejection",
                    ResponseEvidence(invocation.response_path),
                    invocation.diagnostics,
                ) from exc
            raise OperationIssue("image_import_incompatible", details.message, details)
        raise_cel_rejection(
            invocation,
            request.target.layer,
            request.target,
            (request.target.frame_number, request.target.frame_number),
        )
        try:
            evidence = ImageImportEvidence.model_validate(invocation.payload)
            expected_bounds = Rectangle(
                x=request.position.x,
                y=request.position.y,
                width=decoded.width,
                height=decoded.height,
            )
            selected = evidence.cel
            if (
                evidence.image != image
                or evidence.color_profile != profile
                or evidence.before.exists
                or not selected.exists
                or selected.layer_path != evidence.before.layer_path
                or selected.frame_number != request.target.frame_number
                or evidence.before.frame_number != request.target.frame_number
                or selected.image_bounds != expected_bounds
                or selected.position is None
                or selected.position.model_dump() != request.position.model_dump()
                or selected.is_background
                or selected.is_tilemap
                or selected.linked_cels
                or selected.opacity != 255
                or selected.z_index != 0
                or evidence.sprite.metadata.cel_count != evidence.before_cel_count + 1
                or evidence.sprite.metadata.color_mode != decoded.color_mode
            ):
                raise ValueError(
                    "Import evidence differs from decoded input or requested Cel"
                )
            if (
                request.target.layer.layer_path is not None
                and selected.layer_path != request.target.layer.layer_path
            ):
                raise ValueError("Import evidence selects another Layer")
            if decoded.color_mode == "indexed":
                palette = evidence.effective_palette
                if (
                    palette is None
                    or evidence.transparent_index is None
                    or palette.frame_number != request.target.frame_number
                ):
                    raise ValueError("Missing destination Indexed basis")
                used = sorted(set(decoded.stored_bytes))
                if [entry.index for entry in palette.indexes] != used:
                    raise ValueError("Palette evidence omits used indexes")
                for entry in palette.indexes:
                    actual = (
                        entry.color.red,
                        entry.color.green,
                        entry.color.blue,
                        entry.color.alpha,
                    )
                    if entry.index == evidence.transparent_index:
                        actual = (0, 0, 0, 0)
                    if (
                        entry.index >= palette.palette_size
                        or actual != decoded.entries[entry.index]
                    ):
                        raise ValueError(
                            "Destination Palette changes decoded color meaning"
                        )
            elif (
                evidence.effective_palette is not None
                or evidence.transparent_index is not None
            ):
                raise ValueError("RGB import has Indexed evidence")
        except ValueError as exc:
            raise RuntimeIssue(
                "response_malformed",
                str(exc),
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        protect_input()
        return ImageImportResult(
            **evidence.model_dump(),
            raster_file=receipt,
            target_commit=mutation.commit(),
        )


IMAGE_IMPORT_OPERATIONS = (
    OperationDescriptor(
        "image import",
        ImageImportRequest,
        ImageImportResult,
        import_image,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=[
                "aseprite_sprite_inspection",
                "aseprite_cel_lifecycle",
                "aseprite_assign_color_profile",
                "aseprite_palette_entries",
            ],
        ),
        (
            *RUNTIME_FAILURE_CODES,
            *LAYER_ADDRESS_FAILURE_CODES,
            "cel_frame_out_of_bounds",
            "cel_unsupported_target",
            "cel_already_exists",
            "image_import_incompatible",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
