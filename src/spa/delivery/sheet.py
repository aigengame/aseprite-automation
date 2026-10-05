"""Sprite Sheet export: native samples, independently verified files, then publication."""

from pydantic import ValidationError

from spa.authoring.color.palette import EFFECTIVE_PALETTE_RESOURCE
from spa.authoring.color.profile import PROFILE_RESOURCES
from spa.authoring.document.layer import LAYER_SELECT_RESOURCE
from spa.authoring.document.tag import TAG_SELECT_RESOURCE
from spa.authoring.raster.image_snapshot import COMPOSITION_RESOURCE
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    ArtifactVerificationEvidence,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PngInputError,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import PublicModel, RuntimeRequirements
from spa.delivery.export import ExportDestination, ImageArtifact
from spa.delivery.sheet_contracts import (
    ExportSheetRequest,
    ExportSheetResult,
    MetadataArtifact,
    MetadataDestination,
    SheetParameters,
    SheetRejection,
)
from spa.delivery.sheet_publication import staged_sheet
from spa.delivery.sheet_verification import NativeSheet, verify_sheet

SHEET_SUPPORT = PackagedResource(
    "export_sheet_support", "delivery/export_sheet_support.lua"
)
SHEET_RESOURCES = tuple(
    dict.fromkeys(
        (
            *PROFILE_RESOURCES,
            LAYER_SELECT_RESOURCE,
            TAG_SELECT_RESOURCE,
            EFFECTIVE_PALETTE_RESOURCE,
            COMPOSITION_RESOURCE,
            SHEET_SUPPORT,
        )
    )
)
SHEET_HANDLER = PackagedHandler(
    "export_sheet", "delivery/export_sheet.lua", SHEET_RESOURCES
)
SHEET_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_export_sheet"],
)


class NativeSheetRejection(PublicModel):
    message: str
    reason: str


def export_sheet(
    request: ExportSheetRequest, services: OperationServices
) -> ExportSheetResult:
    files, decode = services.artifact_files, services.decode_png_input
    if files is None or decode is None:
        raise RuntimeError(
            "Sprite Sheet export requires Artifact Files and the PNG decoder"
        )
    with staged_sheet(request, files) as staged:
        observation = services.probe_runtime(request)
        image_reference = str(
            staged.image_destination.relative_to(
                staged.metadata_destination.parent, walk_up=True
            )
        )
        parameters = SheetParameters.model_validate(
            {name: getattr(request, name) for name in SheetParameters.model_fields}
        )
        invocation = services.invoke_kernel(
            observation,
            SHEET_HANDLER,
            parameters.model_dump(mode="json", exclude_none=True)
            | {
                "source_sprite_file": request.source_sprite_file,
                "staged_png_file": str(staged.image),
                "staged_metadata_file": str(staged.metadata),
                "staged_pixels_file": str(staged.pixels),
                "staged_trim_png_file": str(staged.trim_image),
                "staged_trim_metadata_file": str(staged.trim_metadata),
                "image_reference": image_reference,
            },
            request.timeout_seconds,
        )
        try:
            if "rejection" in invocation.payload:
                rejection = NativeSheetRejection.model_validate(
                    invocation.payload["rejection"]
                )
                raise OperationIssue(
                    "export_sheet_unsupported",
                    rejection.message,
                    SheetRejection(reason=rejection.reason),
                )
            native = NativeSheet.model_validate(invocation.payload)
        except ValidationError as exc:
            raise RuntimeIssue(
                "response_malformed",
                "Sprite Sheet Kernel returned malformed native facts",
                ResponseEvidence(invocation.response_path),
                invocation.diagnostics,
            ) from exc
        image, metadata, pixels = (
            files.read_staged(path)
            for path in (staged.image, staged.metadata, staged.pixels)
        )
        try:
            png = decode(image.payload)
            frames = verify_sheet(
                request, native, png, metadata.payload, pixels.payload, image_reference
            )
        except (ValueError, KeyError, TypeError, PngInputError) as exc:
            raise RuntimeIssue(
                "artifact_verification_failed",
                "Sprite Sheet files differ from the requested native export",
                ArtifactVerificationEvidence(str(staged.metadata), str(exc)),
                invocation.diagnostics,
            ) from exc
        image_file, metadata_file = staged.publish(image.sha256, metadata.sha256)
        return ExportSheetResult(
            image_destination=ExportDestination(
                path=image_file.path, if_exists=request.image_destination.if_exists
            ),
            metadata_destination=MetadataDestination(
                path=metadata_file.path,
                if_exists=request.metadata_destination.if_exists,
            ),
            requested_parameters=parameters,
            width=png.width,
            height=png.height,
            output_color_mode=png.color_mode,
            color_profile=png.color_profile,
            icc_identity=native.icc_identity,
            srgb_rendering_intent=0 if png.srgb_rendering_intent == 0 else None,
            source_frames=native.source_frames,
            source_tags=native.source_tags,
            selected_tag=native.selected_tag,
            common_trim=native.common_trim,
            effective_background=native.effective_background,
            frames=frames,
            artifacts=(
                ImageArtifact(
                    path=image_file.path,
                    byte_size=image_file.byte_size,
                    sha256=image_file.sha256,
                ),
                MetadataArtifact(
                    path=metadata_file.path,
                    byte_size=metadata_file.byte_size,
                    sha256=metadata_file.sha256,
                ),
            ),
        )


SHEET_OPERATIONS = (
    OperationDescriptor(
        "export sheet",
        ExportSheetRequest,
        ExportSheetResult,
        export_sheet,
        lambda result: "\n".join(artifact.path for artifact in result.artifacts),
        SHEET_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "artifact_file_failed",
            "artifact_verification_failed",
            "export_sheet_unsupported",
            "partial_publication",
        ),
        execution_kind="export",
        side_effects=("publishes a verified PNG texture then JSON Array metadata",),
        probe_before_execute=False,
        help_summary="Export a native Sprite Sheet with one metadata record per selected Frame.",
    ),
)
