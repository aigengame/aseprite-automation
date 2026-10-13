"""PNG-sequence admission, observed-facts projection and error translation."""

from spa.adapters.png_decoding import PngDecodeError, decode_png
from spa.contracts.encoded_animation import AnimationDecodeError, DecodedSequencePng


def decode_sequence_png(payload: bytes) -> DecodedSequencePng:
    """Decode supported PNG samples without defining source or export policy."""
    try:
        decoded = decode_png(
            payload,
            representations=(
                (0, 8),
                (2, 8),
                (3, 1),
                (3, 2),
                (3, 4),
                (3, 8),
                (4, 8),
                (6, 8),
            ),
            representation_error="PNG requires 8-bit channels or 1/2/4/8-bit Palette Indexes",
        )
    except PngDecodeError as exc:
        raise AnimationDecodeError(str(exc)) from exc
    return DecodedSequencePng(
        width=decoded.width,
        height=decoded.height,
        color_mode=decoded.color_mode,
        color_type=decoded.color_type,
        bit_depth=decoded.bit_depth,
        stored_bytes=decoded.stored_bytes,
        rgba_bytes=decoded.rgba_bytes,
        entries=decoded.entries,
        color_profile=decoded.color_profile,
        icc_bytes=decoded.icc_bytes,
        srgb_rendering_intent=decoded.srgb_rendering_intent,
    )
