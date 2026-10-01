"""Static Image Export contract and publication use case."""

from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from spa.authoring.color.profile import PROFILE_FILE_RESOURCE
from spa.contracts.artifact import ArtifactFileDetails, ArtifactVerificationDetails
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PostconditionEvidence,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import (
    FailureCodeSpec,
    PublicModel,
    RuntimeRequest,
    RuntimeRequirements,
)
from spa.delivery.png_publication import staged_png


class ExportDestination(PublicModel):
    # JSON Schema's $ may match before a final newline; reject it explicitly.
    path: str = Field(
        min_length=5,
        pattern=r"^[^\x00\r\n]+\.png$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    if_exists: Literal["fail", "replace"]


class ExportImageRequest(RuntimeRequest):
    source_sprite_file: str = Field(
        min_length=10,
        pattern=r"^[^\x00\r\n]+\.aseprite$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    destination: ExportDestination
    frame_number: int = Field(ge=1)
    color_mode: Literal["preserve"]
    color_profile: Literal["preserve"]
    transparency: Literal["preserve"]


class ImageArtifact(PublicModel):
    role: Literal["image"] = "image"
    path: str
    media_type: Literal["image/png"] = "image/png"
    format: Literal["png"] = "png"
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AlphaChannelFacts(PublicModel):
    present: bool
    minimum: int = Field(ge=0, le=255)
    maximum: int = Field(ge=0, le=255)


class ExportImageResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa export image"] = "spa export image"
    destination: ExportDestination
    frame_number: int = Field(ge=1)
    export_image_area: Literal["canvas"] = "canvas"
    layer_composition: Literal["visible"] = "visible"
    color_mode: Literal["rgb"] = "rgb"
    color_profile: Literal["none", "srgb"]
    alpha_channel: AlphaChannelFacts
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    artifact: ImageArtifact


class NativeImageFacts(PublicModel):
    frame_number: int = Field(ge=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    color_mode: Literal["rgb"]
    color_profile: Literal["none", "srgb"]
    alpha_min: int = Field(ge=0, le=255)
    alpha_max: int = Field(ge=0, le=255)
    rendered_byte_size: int = Field(gt=0)


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
EXPORT_HANDLER = PackagedHandler(
    "export_image", "delivery/export_image.lua", EXPORT_PROBE_RESOURCES
)


def _native_facts(invocation: KernelInvocationResult) -> NativeImageFacts:
    try:
        return NativeImageFacts.model_validate(invocation.payload)
    except ValidationError as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Export Image Kernel returned malformed native facts",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc


def export_image(
    request: ExportImageRequest, services: OperationServices
) -> ExportImageResult:
    files = services.artifact_files
    if files is None:
        raise RuntimeError("Export Image requires the Artifact File Adapter")
    verify_png = services.verify_png
    if verify_png is None:
        raise RuntimeError("Export Image requires the PNG Artifact Verifier")
    with staged_png(
        files,
        verify_png,
        source=Path(request.source_sprite_file),
        destination=request.destination.path,
        if_exists=request.destination.if_exists,
    ) as staged:
        observation = services.probe_runtime(request)
        invocation = services.invoke_kernel(
            observation,
            EXPORT_HANDLER,
            {
                "source_sprite_file": request.source_sprite_file,
                "staged_png_file": str(staged.png_file),
                "staged_rgba_file": str(staged.rgba_file),
                "frame_number": request.frame_number,
                "color_mode": request.color_mode,
                "color_profile": request.color_profile,
                "transparency": request.transparency,
            },
            request.timeout_seconds,
        )
        native = _native_facts(invocation)
        decoded = staged.verify(
            native,
            invocation,
            matches_expected=native.frame_number == request.frame_number,
            mismatch_message="Decoded PNG differs from the native rendered Image",
        )
        if native.alpha_min > native.alpha_max:
            raise RuntimeIssue(
                "postcondition_failed",
                "Native Image reported invalid Alpha Channel bounds",
                PostconditionEvidence(invocation.response_path, "invalid alpha bounds"),
                invocation.diagnostics,
            )
        published = staged.publish()
        return ExportImageResult(
            destination=ExportDestination(
                path=published.path, if_exists=request.destination.if_exists
            ),
            frame_number=request.frame_number,
            color_profile=decoded.color_profile,
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
        ),
        execution_kind="export",
        side_effects=("publishes one verified PNG Image Artifact",),
    ),
)
