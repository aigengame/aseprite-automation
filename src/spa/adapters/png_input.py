"""PNG input/Artifact admission, observed-facts projection and error translation."""

from spa.adapters.png_decoding import PngDecodeError, decode_png
from spa.contracts.ports import PngInputError, PngInputFacts, PngRasterFacts


def _decode_raster[T: PngRasterFacts](
    payload: bytes, allowed_types: tuple[int, ...], facts_type: type[T]
) -> T:
    try:
        decoded = decode_png(
            payload,
            representations=tuple((color_type, 8) for color_type in allowed_types),
            representation_error="PNG representation is outside the requested 8-bit subset",
        )
    except PngDecodeError as exc:
        raise PngInputError(str(exc)) from exc
    return facts_type(
        width=decoded.width,
        height=decoded.height,
        color_mode=decoded.color_mode,
        rgba_bytes=decoded.rgba_bytes,
        stored_bytes=decoded.stored_bytes,
        entries=decoded.entries,
        color_profile=decoded.color_profile,
        icc_bytes=decoded.icc_bytes,
        color_type=decoded.color_type,
        srgb_rendering_intent=decoded.srgb_rendering_intent,
    )


def decode_png_input(payload: bytes) -> PngInputFacts:
    """Keep the accepted external-input RGB/Indexed policy."""
    return _decode_raster(payload, (2, 3, 6), PngInputFacts)


def decode_png_artifact(payload: bytes) -> PngRasterFacts:
    """Decode preserved native RGB, Grayscale, or Indexed PNG output."""
    return _decode_raster(payload, (0, 2, 3, 4, 6), PngRasterFacts)
