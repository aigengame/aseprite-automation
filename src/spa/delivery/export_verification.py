"""Bind a decoded static PNG to native samples and the explicit export choices."""

from pathlib import Path

from spa.authoring.color.profile import supported_icc_identity
from spa.contracts.digest import fnv1a64
from spa.contracts.ports import (
    ArtifactVerificationEvidence,
    PngArtifactDecoder,
    PngFacts,
    PngInputError,
    RuntimeIssue,
)
from spa.delivery.export_contracts import (
    CanvasArea,
    ExportImageRequest,
    NativeImageFacts,
    RectangleArea,
    SliceArea,
)


def matches_request(request: ExportImageRequest, native: NativeImageFacts) -> bool:
    area = native.export_image_area
    rectangle = area.rectangle
    expected = request.export_image_area
    matches_area = area.kind == expected.kind
    if isinstance(expected, RectangleArea):
        matches_area &= rectangle == expected.rectangle
    elif isinstance(expected, CanvasArea):
        matches_area &= (
            rectangle.x == rectangle.y == 0
            and rectangle.width == native.source_canvas.width
            and rectangle.height == native.source_canvas.height
        )
    elif isinstance(expected, SliceArea):
        matches_area &= (
            area.slice_index is not None
            and area.slice_name is not None
            and area.key_frame_number is not None
            and area.key_frame_number <= request.frame_number
            and (
                expected.slice.slice_index is None
                or area.slice_index == expected.slice.slice_index
            )
            and (
                expected.slice.slice_name is None
                or area.slice_name == expected.slice.slice_name
            )
        )
    return (
        matches_area
        and native.frame_number == request.frame_number
        and native.composition_color_mode == request.composition_color_mode
        and native.width == rectangle.width
        and native.height == rectangle.height
        and 0 <= rectangle.x <= native.source_canvas.width - rectangle.width
        and 0 <= rectangle.y <= native.source_canvas.height - rectangle.height
        and native.color_mode
        == (
            native.source_color_mode
            if request.composition_color_mode == "preserve"
            else "rgb"
        )
    )


def verify_export_png(
    payload: bytes, path: Path, decode: PngArtifactDecoder, native: NativeImageFacts
) -> PngFacts:
    try:
        decoded = decode(payload)
        entries = tuple(
            (c.red, c.green, c.blue, c.alpha) for c in native.palette_entries
        )
        if (
            decoded.color_mode != native.color_mode
            or fnv1a64(decoded.stored_bytes) != native.stored_content_digest
            or decoded.entries != entries
            or decoded.color_profile != native.color_profile
            or (
                decoded.color_profile == "icc"
                and (
                    decoded.icc_bytes is None
                    or supported_icc_identity(decoded.icc_bytes) != native.icc_identity
                )
            )
            or (decoded.color_profile != "icc" and native.icc_identity is not None)
            or (decoded.color_profile == "srgb" and decoded.srgb_rendering_intent != 0)
            or (decoded.color_mode == "grayscale" and decoded.color_profile == "icc")
            or (
                decoded.color_mode == "indexed"
                and (
                    native.transparent_index is None
                    or not 1 <= len(entries) <= 256
                    or native.transparent_index >= len(entries)
                    or (
                        not native.effective_background
                        and entries[native.transparent_index][3] != 0
                    )
                )
            )
        ):
            raise ValueError("PNG representation differs from native export facts")
        alphas = decoded.rgba_bytes[3::4]
        return PngFacts(
            decoded.width,
            decoded.height,
            decoded.color_profile,
            decoded.color_type in (4, 6) or any(alpha < 255 for alpha in alphas),
            min(alphas),
            max(alphas),
            decoded.rgba_bytes,
        )
    except (PngInputError, ValueError) as exc:
        raise RuntimeIssue(
            "artifact_verification_failed",
            "Static PNG failed independent verification",
            ArtifactVerificationEvidence(str(path), str(exc)),
        ) from exc
