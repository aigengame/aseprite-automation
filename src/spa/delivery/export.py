"""Static Image Export: native composition and color, verified PNG publication."""

from pathlib import Path

from pydantic import ValidationError

from spa.authoring.color.color_mode import (
    COLOR_MODE_FAILURE_SPECS,
    COLOR_MODE_RESOURCES,
    reject_color_mode,
)
from spa.authoring.color.palette import PALETTE_TRANSFORM_HANDLER
from spa.authoring.color.palette_file import (
    PALETTE_FILE_FAILURE_SPECS,
    PALETTE_FILE_RESOURCE,
    read_palette_file,
    reject_palette_file,
)
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
from spa.authoring.color.quantization import (
    PALETTE_QUANTIZATION_RESOURCE,
    QUANTIZATION_FAILURE_SPECS,
    reject_quantization,
)
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
    ArtifactVerificationEvidence,
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    ResponseEvidence,
    RuntimeCompatibilityEvidence,
    RuntimeIssue,
)
from spa.contracts.public import (
    CapabilityGap,
    FailureCodeSpec,
    RuntimeCapability,
    RuntimeRequirements,
)
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
    ImportedExportPalette,
    NativeImageFacts,
    QuantizedExportPalette,
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


def export_image_capability_gaps(
    aseprite_version: str, verified_capabilities: list[RuntimeCapability]
) -> list[CapabilityGap]:
    return [
        CapabilityGap(
            capability=f"spa export image: {choice}",
            aseprite_version=aseprite_version,
            evidence=f"{capability} was not observed; requests using this choice are refused",
        )
        for choice, capability in (
            ("assign profile", "aseprite_assign_color_profile"),
            ("convert profile", "aseprite_convert_color_profile"),
            ("change color mode", "aseprite_change_color_mode"),
            ("import palette", "aseprite_palette_files"),
            ("quantize palette", "aseprite_palette_quantization"),
            ("opaque background", "aseprite_background_conversion"),
        )
        if capability not in verified_capabilities
    ]


def _native_facts(
    request: ExportImageRequest, invocation: KernelInvocationResult
) -> NativeImageFacts:
    try:
        if "rejection" in invocation.payload:
            rejected = invocation.payload["rejection"]
            code = rejected["code"]
            if code in {item.code for item in PROFILE_FAILURE_SPECS}:
                reject_profile(invocation)
            if code in {item.code for item in COLOR_MODE_FAILURE_SPECS}:
                reject_color_mode(invocation, rejected)
            if code in {item.code for item in PALETTE_FILE_FAILURE_SPECS}:
                reject_palette_file(invocation)
            if code in {item.code for item in QUANTIZATION_FAILURE_SPECS}:
                reject_quantization(invocation)
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
    imported_palette = None
    if isinstance(request.palette_preparation, ImportedExportPalette):
        raw, imported_palette = read_palette_file(
            request.palette_preparation.palette_file, services
        )
        payload["palette_preparation"]["palette_file_bytes"] = raw.hex()
    profile = request.color_profile
    assigned_icc_identity = None
    if isinstance(profile, (AssignExportProfile, ConvertExportProfile)):
        prepared = profile_payload(profile, services)
        if isinstance(profile.profile, IccProfile):
            assigned_icc_identity = supported_icc_identity(
                bytes.fromhex(prepared["icc_bytes"])
            )
        if isinstance(profile.profile, IccProfile) and assigned_icc_identity is None:
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
        capability: RuntimeCapability | None = (
            "aseprite_assign_color_profile"
            if isinstance(profile, AssignExportProfile)
            else "aseprite_convert_color_profile"
            if isinstance(profile, ConvertExportProfile)
            else None
        )
        required: set[RuntimeCapability] = (
            {capability} if capability is not None else set()
        )
        if request.color_mode != "preserve":
            required.add("aseprite_change_color_mode")
        if isinstance(request.palette_preparation, ImportedExportPalette):
            required.add("aseprite_palette_files")
        if isinstance(request.palette_preparation, QuantizedExportPalette):
            required.add("aseprite_palette_quantization")
        if request.transparency != "preserve":
            required.add("aseprite_background_conversion")
        missing = required - set(observation.verified_capabilities)
        if missing:
            raise RuntimeIssue(
                "runtime_incompatible",
                "A requested native export behavior is unavailable",
                RuntimeCompatibilityEvidence(
                    aseprite_version=observation.aseprite_version,
                    lua_version=observation.lua_version,
                    api_version=observation.api_version,
                    required_lua_language="Lua 5.4",
                    minimum_api_version=41,
                    missing_capabilities=tuple(sorted(missing)),
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
        imported_entries = (
            tuple(
                (c.red, c.green, c.blue, c.alpha)
                for c in native.imported_palette_entries
            )
            if native.imported_palette_entries is not None
            else None
        )
        if imported_entries != (imported_palette.entries if imported_palette else None):
            raise RuntimeIssue(
                "artifact_verification_failed",
                "Native Palette import differs from independent file decoding",
                ArtifactVerificationEvidence(
                    str(staged.png_file), "ordered Palette Entries differ"
                ),
                invocation.diagnostics,
            )
        decoded = staged.verify(
            native,
            invocation,
            matches_expected=matches_request(
                request, native, assigned_icc_identity=assigned_icc_identity
            ),
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
            *(spec.code for spec in COLOR_MODE_FAILURE_SPECS),
            *(spec.code for spec in PALETTE_FILE_FAILURE_SPECS),
            *(spec.code for spec in QUANTIZATION_FAILURE_SPECS),
        ),
        execution_kind="export",
        side_effects=("publishes one verified PNG Image Artifact",),
        probe_before_execute=False,
        help_summary=(
            "Export one Frame: select Canvas/Rectangle/Slice and visible/include Layers, "
            "compose in preserve/rgb mode, then apply Profile, Palette preparation, "
            "Color Mode, and transparency choices before verified PNG publication."
        ),
    ),
)
