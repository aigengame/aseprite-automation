"""Palette file import contracts and native mutation orchestration."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from spa.application.mutation import prepare_mutation
from spa.authoring.color.palette import (
    PALETTE_TRANSFORM_HANDLER,
    PaletteMutationRequest,
    PaletteSetEvidence,
    reject_palette,
)
from spa.contracts.mutation import TargetCommit
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    ArtifactVerificationEvidence,
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PaletteFileError,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequirements


class GplPaletteFile(PublicModel):
    format: Literal["gpl"]
    path: str = Field(
        min_length=5,
        pattern=r"^[^\x00\r\n]+\.gpl$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )


class PngPaletteFile(PublicModel):
    format: Literal["png"]
    path: str = Field(
        min_length=5,
        pattern=r"^[^\x00\r\n]+\.png$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )


PaletteFileInput = Annotated[
    GplPaletteFile | PngPaletteFile, Field(discriminator="format")
]


class PaletteImportRequest(PaletteMutationRequest):
    palette_frame_number: int = Field(ge=1)
    palette_file: PaletteFileInput


class PaletteFileReceipt(PublicModel):
    """Verified file facts shared by consumed input and produced Palette Artifacts."""

    role: Literal["palette"] = "palette"
    format: Literal["gpl", "png"]
    media_type: Literal["text/plain", "image/png"]
    path: str
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PaletteImportResult(PaletteSetEvidence):
    status: Literal["success"] = "success"
    operation: Literal["spa palette import"] = "spa palette import"
    palette_file: PaletteFileReceipt
    target_commit: TargetCommit


class PaletteFileDetails(PublicModel):
    kind: Literal["palette_file"] = "palette_file"
    path: str
    reason: Literal["unreadable", "invalid", "native_load_failed"]
    message: str


PALETTE_FILE_FAILURE_SPECS = (
    FailureCodeSpec(
        "palette_file_failed",
        "The input Palette file could not be decoded without loss",
        "input",
        PaletteFileDetails,
    ),
)
PALETTE_FILE_RESOURCE = PackagedResource("palette_file", "color/palette_file.lua")
PALETTE_IMPORT_HANDLER = PackagedHandler(
    "palette_import",
    "color/palette_transform_run.lua",
    (*PALETTE_TRANSFORM_HANDLER.support_resources, PALETTE_FILE_RESOURCE),
)


def reject_palette_file(invocation: KernelInvocationResult) -> None:
    rejected = invocation.payload.get("rejection")
    if rejected is None or rejected.get("code") != "palette_file_failed":
        reject_palette(invocation)
        return
    try:
        details = PaletteFileDetails.model_validate(rejected["details"])
    except (KeyError, ValueError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Invalid Palette-file rejection",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc
    raise OperationIssue("palette_file_failed", details.message, details)


def import_palette(
    request: PaletteImportRequest, services: OperationServices
) -> PaletteImportResult:
    files, decode = services.artifact_files, services.decode_palette_file
    assert files is not None and decode is not None, (
        "Palette import requires file services"
    )
    path = request.palette_file.path
    try:
        raw = files.read_input(Path(path))
    except RuntimeIssue as exc:
        raise OperationIssue(
            "palette_file_failed",
            "Palette file could not be read",
            PaletteFileDetails(
                path=path, reason="unreadable", message="Cannot read Palette file"
            ),
        ) from exc
    try:
        decoded = decode(raw, request.palette_file.format)
    except PaletteFileError as exc:
        raise OperationIssue(
            "palette_file_failed",
            "Palette file is invalid",
            PaletteFileDetails(path=path, reason="invalid", message=str(exc)),
        ) from exc
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
            PALETTE_IMPORT_HANDLER,
            {
                "operation": "import",
                "source_sprite_file": request.source_sprite_file,
                "staged_sprite_file": str(mutation.staged_sprite_file),
                "palette_frame_number": str(request.palette_frame_number),
                "palette_file": request.palette_file.model_dump(),
                "palette_file_bytes": raw.hex(),
            },
            request.timeout_seconds,
        )
        reject_palette_file(invocation)
        try:
            evidence = PaletteSetEvidence.model_validate(invocation.payload)
            selected = next(
                c
                for c in evidence.palette_changes
                if c.palette_frame_number == request.palette_frame_number
            )
            if selected != evidence.palette:
                raise ValueError("Wrong Palette Change in import evidence")
        except (ValueError, StopIteration) as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Invalid persisted Palette import evidence",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        colors = tuple(
            (e.color.red, e.color.green, e.color.blue, e.color.alpha)
            for e in selected.entries
        )
        if colors != decoded.entries:
            raise RuntimeIssue(
                "artifact_verification_failed",
                "Native Palette import differs from independent file decoding",
                ArtifactVerificationEvidence(path, "ordered Palette Entries differ"),
                invocation.diagnostics,
            )
        return PaletteImportResult(
            **evidence.model_dump(),
            target_commit=mutation.commit(),
            palette_file=PaletteFileReceipt(
                path=path,
                format=request.palette_file.format,
                media_type="text/plain"
                if request.palette_file.format == "gpl"
                else "image/png",
                byte_size=decoded.byte_size,
                sha256=decoded.sha256,
            ),
        )


PALETTE_FILE_OPERATIONS = (
    OperationDescriptor(
        "palette import",
        PaletteImportRequest,
        PaletteImportResult,
        import_palette,
        lambda result: result.target_commit.target_sprite_file,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=[
                "aseprite_sprite_inspection",
                "aseprite_palette_entries",
                "aseprite_palette_resize",
                "aseprite_palette_files",
            ],
        ),
        (
            *RUNTIME_FAILURE_CODES,
            "palette_file_failed",
            "palette_change_missing",
            "palette_persistence_failed",
            "palette_transform_rejected",
            "palette_index_out_of_bounds",
            "artifact_verification_failed",
            "target_commit_failed",
        ),
        execution_kind="mutation",
        side_effects=("publishes the declared Target Sprite File",),
    ),
)
