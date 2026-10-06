"""Static Image Export: native composition and color, verified PNG publication."""

from pathlib import Path

from pydantic import ValidationError

from spa.authoring.color.color_mode import COLOR_MODE_RESOURCES
from spa.authoring.color.palette import PALETTE_TRANSFORM_HANDLER
from spa.authoring.color.palette_file import PALETTE_FILE_RESOURCE
from spa.authoring.color.profile import (
    PROFILE_FAILURE_SPECS,
    PROFILE_FILE_RESOURCE,
    PROFILE_RESOURCES,
    IccProfile,
    ProfileFileDetails,
    profile_payload,
    reject_profile,
    supported_icc_identity,
)
from spa.authoring.color.quantization import PALETTE_QUANTIZATION_RESOURCE
from spa.authoring.document.layer import LAYER_MUTATE_HANDLER
from spa.authoring.document.slice import SLICE_RESOURCE, SliceTargetDetails
from spa.authoring.document.targets import (
    LAYER_ADDRESS_FAILURE_CODES,
    LayerTargetDetails,
)
from spa.authoring.raster.image_snapshot import COMPOSITION_RESOURCE
from spa.contracts.artifact import ArtifactFileDetails, ArtifactVerificationDetails
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeCompatibilityEvidence,
    RuntimeIssue,
)
from spa.contracts.public import FailureCodeSpec, RuntimeRequirements
from spa.delivery.export_contracts import (
    AlphaChannelFacts,
    AssignExportProfile,
    ConvertExportProfile,
    ExportDestination,
    ExportImageDetails,
    ExportImageParameters,
    ExportImageRequest,
    ExportImageResult,
    ImageArtifact,
    NativeImageFacts,
    SliceArea,
)
from spa.delivery.export_verification import matches_request, verify_export_png
from spa.delivery.png_publication import staged_png

EXPORT_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "artifact_file_failed",
        "The staged Artifact or its Export Destination could not be prepared or published",
        "execution",
        ArtifactFileDetails,
    ),
    FailureCodeSpec(
        "artifact_verification_failed",
        "The staged Artifact did not match native observations",
        "execution",
        ArtifactVerificationDetails,
    ),
    FailureCodeSpec(
        "export_image_invalid",
        "The selected Source or native operations cannot satisfy the static PNG request",
        "input",
        ExportImageDetails,
    ),
)
EXPORT_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_export_image"],
)
EXPORT_SUPPORT = PackagedResource(
    "export_image_support", "delivery/export_image_support.lua"
)
EXPORT_PROBE_RESOURCES = (EXPORT_SUPPORT, PROFILE_FILE_RESOURCE)
EXPORT_PIPELINE = PackagedResource(
    "export_image_pipeline", "delivery/export_image_pipeline.lua"
)
EXPORT_HANDLER = PackagedHandler(
    "export_image",
    "delivery/export_image.lua",
    tuple(
        dict.fromkeys(
            (
                *PROFILE_RESOURCES,
                *COLOR_MODE_RESOURCES,
                *PALETTE_TRANSFORM_HANDLER.support_resources,
                *LAYER_MUTATE_HANDLER.support_resources,
                SLICE_RESOURCE,
                COMPOSITION_RESOURCE,
                PALETTE_FILE_RESOURCE,
                PALETTE_QUANTIZATION_RESOURCE,
                EXPORT_SUPPORT,
                EXPORT_PIPELINE,
            )
        )
    ),
)


def _native_facts(
    request: ExportImageRequest, invocation: KernelInvocationResult
) -> NativeImageFacts:
    try:
        if "rejection" in invocation.payload:
            rejected = invocation.payload["rejection"]
            code = rejected["code"]
            if code in {item.code for item in PROFILE_FAILURE_SPECS}:
                reject_profile(invocation)
            if code in ("slice_missing", "slice_ambiguous"):
                assert isinstance(request.export_image_area, SliceArea)
                raise OperationIssue(
                    code,
                    rejected["message"],
                    SliceTargetDetails(address=request.export_image_area.slice),
                )
            if code in LAYER_ADDRESS_FAILURE_CODES:
                choice = request.layer_composition
                assert choice.mode == "include"
                address = choice.layers[rejected["selector_number"] - 1]
                raise OperationIssue(
                    code,
                    rejected["message"],
                    LayerTargetDetails(address_role="target", address=address),
                )
            raise OperationIssue(
                "export_image_invalid",
                rejected["message"],
                ExportImageDetails(reason=rejected.get("reason", code)),
            )
        return NativeImageFacts.model_validate(invocation.payload)
    except (ValidationError, KeyError, TypeError, IndexError, AssertionError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Export Image Kernel returned malformed native facts",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc


def export_image(
    request: ExportImageRequest, services: OperationServices
) -> ExportImageResult:
    files, decode = services.artifact_files, services.decode_png_artifact
    if files is None or decode is None:
        raise RuntimeError(
            "Export Image requires Artifact Files and the PNG Artifact Decoder"
        )
    parameters = ExportImageParameters.model_validate(
        {name: getattr(request, name) for name in ExportImageParameters.model_fields}
    )
    payload = parameters.model_dump(mode="json", exclude_none=True)
    profile = request.color_profile
    if isinstance(profile, (AssignExportProfile, ConvertExportProfile)):
        prepared = profile_payload(profile, services)
        if (
            isinstance(profile.profile, IccProfile)
            and supported_icc_identity(bytes.fromhex(prepared["icc_bytes"])) is None
        ):
            raise OperationIssue(
                "color_profile_file_failed",
                "The requested ICC is outside the static PNG support set",
                ProfileFileDetails(
                    path=profile.profile.icc_file, reason="unsupported_profile"
                ),
            )
        payload["color_profile"] = {"kind": profile.kind, **prepared}
    with staged_png(
        files,
        lambda payload, path: verify_export_png(payload, path, decode, native),
        source=Path(request.source_sprite_file),
        destination=request.destination.path,
        if_exists=request.destination.if_exists,
    ) as staged:
        observation = services.probe_runtime(request)
        capability = (
            "aseprite_assign_color_profile"
            if isinstance(profile, AssignExportProfile)
            else "aseprite_convert_color_profile"
            if isinstance(profile, ConvertExportProfile)
            else None
        )
        if (
            capability is not None
            and capability not in observation.verified_capabilities
        ):
            raise RuntimeIssue(
                "runtime_incompatible",
                "The requested export Profile behavior is unavailable",
                RuntimeCompatibilityEvidence(
                    aseprite_version=observation.aseprite_version,
                    lua_version=observation.lua_version,
                    api_version=observation.api_version,
                    required_lua_language="Lua 5.4",
                    minimum_api_version=41,
                    missing_capabilities=(capability,),
                ),
            )
        invocation = services.invoke_kernel(
            observation,
            EXPORT_HANDLER,
            payload
            | {
                "source_sprite_file": request.source_sprite_file,
                "staged_png_file": str(staged.png_file),
                "staged_rgba_file": str(staged.rgba_file),
            },
            request.timeout_seconds,
        )
        native = _native_facts(request, invocation)
        decoded = staged.verify(
            native,
            invocation,
            matches_expected=matches_request(request, native),
            mismatch_message="Decoded PNG differs from the native rendered Image",
        )
        published = staged.publish()
        return ExportImageResult(
            destination=ExportDestination(
                path=published.path, if_exists=request.destination.if_exists
            ),
            frame_number=request.frame_number,
            requested_parameters=parameters,
            export_image_area=native.export_image_area,
            layer_composition=request.layer_composition,
            composition_color_mode=request.composition_color_mode,
            source_color_mode=native.source_color_mode,
            resolved_layer_paths=native.resolved_layer_paths,
            effective_background=native.effective_background,
            color_mode=native.color_mode,
            color_profile=decoded.color_profile,
            icc_identity=native.icc_identity,
            srgb_rendering_intent=0 if decoded.color_profile == "srgb" else None,
            transparent_index=native.transparent_index,
            palette_entries=native.palette_entries,
            alpha_channel=AlphaChannelFacts(
                present=decoded.alpha_channel_present,
                minimum=decoded.alpha_min,
                maximum=decoded.alpha_max,
            ),
            width=decoded.width,
            height=decoded.height,
            artifact=ImageArtifact(
                path=published.path,
                byte_size=published.byte_size,
                sha256=published.sha256,
            ),
        )


EXPORT_OPERATIONS = (
    OperationDescriptor(
        "export image",
        ExportImageRequest,
        ExportImageResult,
        export_image,
        lambda result: result.artifact.path,
        EXPORT_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            "artifact_file_failed",
            "artifact_verification_failed",
            "export_image_invalid",
            *LAYER_ADDRESS_FAILURE_CODES,
            "slice_missing",
            "slice_ambiguous",
            *(spec.code for spec in PROFILE_FAILURE_SPECS),
        ),
        execution_kind="export",
        side_effects=("publishes one verified PNG Image Artifact",),
        probe_before_execute=False,
        help_summary="Export one explicit Frame, Canvas area and Layer Composition as a verified PNG.",
    ),
)
