"""Freeze, prepare, independently verify, and publish one selected raster."""

import hashlib
from dataclasses import dataclass
from importlib.resources import files as packaged_files
from pathlib import Path
from typing import Literal, NoReturn, cast

from pydantic import Field

from spa.authoring.color.color_mode import (
    COLOR_MODE_RESOURCES,
    DitheringEvidence,
    MappingEvidence,
)
from spa.authoring.color.palette import PALETTE_TRANSFORM_HANDLER
from spa.authoring.color.profile import PROFILE_ICC_RESOURCES, PROFILE_RESOURCES
from spa.authoring.raster.image import (
    IMAGE_CANVAS_TRANSFORM_RESOURCE,
    IMAGE_RESIZE_TRANSFORM_RESOURCE,
    ImageCanvasOffset,
    ImageCropRectangle,
)
from spa.contracts.digest import fnv1a64
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    ArtifactVerificationEvidence,
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PngFacts,
    PngInputDecoder,
    PngInputError,
    PngInputFacts,
    ResponseEvidence,
    RuntimeCompatibilityEvidence,
    RuntimeIssue,
)
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequirements
from spa.contracts.raster import RgbaColor
from spa.delivery.export import EXPORT_SUPPORT, ImageArtifact
from spa.delivery.png_publication import staged_png
from spa.preparation.contracts import (
    ExplicitCrop,
    InputIdentity,
    PreparationGeometry,
    PreparationProfile,
    PreparationRuntime,
    PreparedContent,
    PrepareRasterRequest,
    PrepareRasterResult,
    RasterSize,
    ReproducePreparation,
    ReproductionRecord,
    preparation_geometry,
)

PreparationRefusal = Literal[
    "input",
    "changed_input",
    "reproduction",
    "color_profile",
    "geometry",
    "native_input",
    "mapping",
]


class PreparationDetails(PublicModel):
    kind: Literal["preparation"] = "preparation"
    reason: PreparationRefusal
    message: str


PREPARATION_FAILURE_SPECS = (
    FailureCodeSpec(
        "preparation_rejected",
        "The input or specification cannot be prepared as declared",
        "input",
        PreparationDetails,
    ),
)
PREPARATION_HANDLER = PackagedHandler(
    "raster_prepare",
    "preparation/raster_prepare.lua",
    tuple(
        dict.fromkeys(
            (
                *PROFILE_RESOURCES,
                *COLOR_MODE_RESOURCES,
                *PALETTE_TRANSFORM_HANDLER.support_resources,
                IMAGE_CANVAS_TRANSFORM_RESOURCE,
                IMAGE_RESIZE_TRANSFORM_RESOURCE,
                EXPORT_SUPPORT,
                PackagedResource("image_alpha", "raster/image/image_alpha.lua"),
            )
        )
    ),
)


class NativePreparation(PublicModel):
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)
    color_profile: Literal["none", "srgb"]
    alpha_min: int = Field(ge=0, le=255)
    alpha_max: int = Field(ge=0, le=255)
    rendered_byte_size: int = Field(gt=0)
    source_rgba_digest: str = Field(pattern=r"^[0-9a-f]{16}$")
    normalized_rgba_digest: str = Field(pattern=r"^[0-9a-f]{16}$")
    normalized_alpha_preserved: Literal[True]
    profile: PreparationProfile
    crop: ImageCropRectangle
    resized: RasterSize
    offset: ImageCanvasOffset
    mapping: MappingEvidence
    dithering: DitheringEvidence
    palette_entries: list[RgbaColor]
    transparent_index: int = Field(ge=0, le=255)
    output_mode: Literal["rgba", "indexed"]
    stored_content_digest: str = Field(pattern=r"^[0-9a-f]{16}$")
    rgba_content_digest: str = Field(pattern=r"^[0-9a-f]{16}$")


def _reject(reason: PreparationRefusal, message: str) -> NoReturn:
    raise OperationIssue(
        "preparation_rejected",
        message,
        PreparationDetails(reason=reason, message=message),
    )


def _source_profile(decoded: PngInputFacts) -> PreparationProfile:
    identity = None
    if decoded.color_profile == "icc":
        package = packaged_files("spa.kernel")
        identity = next(
            (
                resource.parameter_name.removeprefix("profile_")
                for resource in PROFILE_ICC_RESOURCES
                if package.joinpath(resource.package_path).read_bytes()
                == decoded.icc_bytes
            ),
            None,
        )
        if identity is None:
            _reject(
                "color_profile",
                "Source ICC is outside the native Color Profile owner's supported set",
            )
    return PreparationProfile.model_validate(
        {
            "source_kind": decoded.color_profile,
            "source_icc_identity": identity,
            "assumption": "srgb" if decoded.color_profile == "none" else None,
            "effective": "srgb",
            "converted": decoded.color_profile == "icc",
        }
    )


def _geometry(
    request: PrepareRasterRequest, decoded: PngInputFacts
) -> PreparationGeometry:
    spec = request.specification
    try:
        RasterSize(width=decoded.width, height=decoded.height)
        if isinstance(spec.crop, ExplicitCrop):
            crop = spec.crop.rectangle
        else:
            # Independent input observations establish expected opaque bounds;
            # the native Raster owner checks these after alpha normalization.
            left, top, right, bottom = decoded.width, decoded.height, -1, -1
            for index, alpha in enumerate(decoded.rgba_bytes[3::4]):
                if alpha >= spec.alpha_threshold:
                    x, y = index % decoded.width, index // decoded.width
                    left, top, right, bottom = (
                        min(left, x),
                        min(top, y),
                        max(right, x),
                        max(bottom, y),
                    )
            if right < left:
                raise ValueError("Automatic crop has no nontransparent pixels")
            crop = ImageCropRectangle(
                x=left, y=top, width=right - left + 1, height=bottom - top + 1
            )
        if (
            crop.x < 0
            or crop.y < 0
            or crop.x + crop.width > decoded.width
            or crop.y + crop.height > decoded.height
        ):
            raise ValueError(
                "Crop Rectangle must be fully contained in the input raster"
            )
        return preparation_geometry(spec, crop)
    except ValueError as exc:
        _reject("geometry", str(exc))


def _native(invocation: KernelInvocationResult) -> NativePreparation:
    try:
        rejection = invocation.payload.get("rejection")
        if rejection is not None:
            if rejection["code"] != "preparation_rejected":
                raise ValueError("Unknown preparation rejection")
            details = PreparationDetails.model_validate(rejection["details"])
            _reject(details.reason, details.message)
        return NativePreparation.model_validate(invocation.payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            "Invalid native preparation evidence",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc


@dataclass(frozen=True)
class _VerifiedPng(PngFacts):
    stored_sha256: str


def _verify_output(
    payload: bytes,
    staged: Path,
    decode: PngInputDecoder,
    request: PrepareRasterRequest,
    native: NativePreparation,
) -> _VerifiedPng:
    try:
        decoded = decode(payload)
        spec = request.specification
        expected_mode = "rgb" if spec.output_mode == "rgba" else "indexed"
        entries = tuple((c.red, c.green, c.blue, c.alpha) for c in spec.palette.entries)
        allowed = set(entries)
        pixels = zip(*[iter(decoded.rgba_bytes)] * 4)
        if (
            decoded.color_mode != expected_mode
            or decoded.color_type != (6 if spec.output_mode == "rgba" else 3)
            or decoded.color_profile != "srgb"
            or decoded.srgb_rendering_intent != 0
            or decoded.icc_bytes is not None
            or fnv1a64(decoded.stored_bytes) != native.stored_content_digest
            or fnv1a64(decoded.rgba_bytes) != native.rgba_content_digest
            or any(pixel not in allowed for pixel in pixels)
            or (spec.output_mode == "indexed" and decoded.entries != entries)
        ):
            raise ValueError(
                "Encoded representation, Palette, colors, or complete pixels differ"
            )
        alphas = decoded.rgba_bytes[3::4]
        return _VerifiedPng(
            decoded.width,
            decoded.height,
            "srgb",
            True,
            min(alphas),
            max(alphas),
            decoded.rgba_bytes,
            hashlib.sha256(decoded.stored_bytes).hexdigest(),
        )
    except (PngInputError, ValueError) as exc:
        raise RuntimeIssue(
            "artifact_verification_failed",
            "Prepared PNG failed independent verification",
            ArtifactVerificationEvidence(str(staged), str(exc)),
        ) from exc


def prepare_raster(
    request: PrepareRasterRequest, services: OperationServices
) -> PrepareRasterResult:
    files, decode = services.artifact_files, services.decode_png_input
    assert files is not None and decode is not None, (
        "Preparation requires Artifact files and PNG decoding"
    )
    raw = files.read_input(Path(request.raster_file))
    identity = (
        InputIdentity(byte_size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if raw
        else None
    )
    if isinstance(request.intent, ReproducePreparation):
        expected = request.intent.expected
        if expected.source_identity != identity:
            _reject(
                "changed_input",
                "Input bytes differ from the caller's retained identity",
            )
        if expected.specification != request.specification:
            _reject(
                "reproduction",
                "The Preparation Specification differs from the retained record",
            )
    try:
        decoded = decode(raw)
    except PngInputError as exc:
        _reject("input", str(exc))
    if decoded.color_mode != "rgb":
        _reject("input", "Preparation requires an 8-bit RGB/RGBA PNG input")
    assert identity is not None
    profile = _source_profile(decoded)
    geometry = _geometry(request, decoded)
    runtime = services.probe_runtime(request)
    if (
        profile.converted
        and "aseprite_convert_color_profile" not in runtime.verified_capabilities
    ):
        raise RuntimeIssue(
            "runtime_incompatible",
            "ICC normalization requires native Color Profile conversion",
            RuntimeCompatibilityEvidence(
                aseprite_version=runtime.aseprite_version,
                lua_version=runtime.lua_version,
                api_version=runtime.api_version,
                required_lua_language="Lua 5.4",
                minimum_api_version=41,
                missing_capabilities=("aseprite_convert_color_profile",),
            ),
        )
    runtime_facts = PreparationRuntime(
        aseprite_version=runtime.aseprite_version,
        api_version=runtime.api_version,
        lua_version=runtime.lua_version,
    )
    if (
        isinstance(request.intent, ReproducePreparation)
        and request.intent.expected.runtime != runtime_facts
    ):
        _reject(
            "reproduction", "Reproduction requires the recorded native runtime choices"
        )
    # Verification remains within the existing scoped Artifact publication boundary.
    # The closure supplies only preparation's expected format policy to the decoder.
    with staged_png(
        files,
        lambda payload, path: _verify_output(payload, path, decode, request, native),
        source=Path(request.raster_file),
        destination=request.destination.path,
        if_exists=request.destination.if_exists,
    ) as staged:
        invocation = services.invoke_kernel(
            runtime,
            PREPARATION_HANDLER,
            {
                "raster_bytes": raw.hex(),
                "decoded": {
                    "width": decoded.width,
                    "height": decoded.height,
                    "rgba_bytes": decoded.rgba_bytes.hex(),
                    "color_profile": decoded.color_profile,
                    "icc_bytes": decoded.icc_bytes.hex()
                    if decoded.icc_bytes is not None
                    else None,
                },
                "specification": request.specification.model_dump(),
                "geometry": geometry.model_dump(),
                "staged_png_file": str(staged.png_file),
                "staged_rgba_file": str(staged.rgba_file),
            },
            request.timeout_seconds,
        )
        native = _native(invocation)
        spec = request.specification
        agrees = (
            native.width == spec.canvas.width
            and native.height == spec.canvas.height
            and native.color_profile == "srgb"
            and native.profile == profile
            and native.crop == geometry.crop
            and native.resized == geometry.resized
            and native.offset == geometry.offset
            and native.source_rgba_digest == fnv1a64(decoded.rgba_bytes)
            and (
                profile.converted
                or native.normalized_rgba_digest == native.source_rgba_digest
            )
            and native.palette_entries == spec.palette.entries
            and native.transparent_index == spec.palette.transparent_index
            and native.output_mode == spec.output_mode
            and native.mapping.requested_rgb_map_algorithm
            == spec.mapping.rgb_map_algorithm
            and native.mapping.effective_rgb_map_algorithm
            == (
                "octree"
                if spec.mapping.rgb_map_algorithm == "default"
                else spec.mapping.rgb_map_algorithm
            )
            and native.mapping.color_best_fit_criteria
            == spec.mapping.color_best_fit_criteria
            and native.dithering
            == DitheringEvidence(
                requested_algorithm="none",
                effective_algorithm="none",
                matrix=None,
                dithering_factor=None,
                effective_factor_percent=None,
            )
        )
        output = cast(
            _VerifiedPng,
            staged.verify(
                native,
                invocation,
                matches_expected=agrees,
                mismatch_message="Prepared raster differs from the declared input or specification",
            ),
        )
        record = ReproductionRecord(
            source_identity=identity,
            specification=spec,
            geometry=geometry,
            runtime=runtime_facts,
            mapping=native.mapping,
            dithering=native.dithering,
            profile=profile,
            content=PreparedContent(
                width=output.width,
                height=output.height,
                output_mode=spec.output_mode,
                rgba_sha256=hashlib.sha256(output.rgba_bytes).hexdigest(),
                stored_sha256=output.stored_sha256,
                palette=spec.palette,
                alpha_min=cast(Literal[0, 255], output.alpha_min),
                alpha_max=cast(Literal[0, 255], output.alpha_max),
            ),
        )
        if (
            isinstance(request.intent, ReproducePreparation)
            and request.intent.expected != record
        ):
            _reject(
                "reproduction",
                "Prepared pixels or format facts differ from the retained record",
            )
        published = staged.publish()
        return PrepareRasterResult(
            raster_file=request.raster_file,
            reproduction=record,
            artifact=ImageArtifact(
                path=published.path,
                byte_size=published.byte_size,
                sha256=published.sha256,
            ),
        )


PREPARATION_OPERATIONS = (
    OperationDescriptor(
        "raster prepare",
        PrepareRasterRequest,
        PrepareRasterResult,
        prepare_raster,
        lambda result: result.artifact.path,
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=[
                "aseprite_assign_color_profile",
                "aseprite_change_color_mode",
                "aseprite_palette_entries",
                "aseprite_palette_resize",
                "aseprite_image_canvas_transform",
                "aseprite_image_resize",
                "aseprite_export_image",
            ],
        ),
        (
            *RUNTIME_FAILURE_CODES,
            "preparation_rejected",
            "artifact_file_failed",
            "artifact_verification_failed",
        ),
        execution_kind="export",
        side_effects=("publishes one verified Prepared Raster PNG",),
        probe_before_execute=False,
        help_summary="Prepare a frozen RGB/RGBA PNG with explicit geometry, anchors, palette, and sRGB output. ICC input requires native Color Profile conversion.",
    ),
)
