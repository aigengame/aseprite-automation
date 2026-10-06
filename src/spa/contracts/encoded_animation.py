"""Independent byte observations for animation delivery decoders."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal


class AnimationDecodeError(ValueError):
    """The supplied bytes do not form a supported complete encoded artifact."""


@dataclass(frozen=True)
class DecodedSequencePng:
    """RGBA for RGB, LA for Grayscale, and unpacked Indexes for Indexed samples."""

    width: int
    height: int
    color_mode: Literal["rgb", "grayscale", "indexed"]
    color_type: int
    bit_depth: int
    stored_bytes: bytes
    rgba_bytes: bytes
    entries: tuple[tuple[int, int, int, int], ...]
    color_profile: Literal["none", "srgb", "icc"]
    icc_bytes: bytes | None
    srgb_rendering_intent: int | None


@dataclass(frozen=True)
class DecodedGifFrame:
    """Full logical-screen pixels and the encoded (x, y, width, height) rectangle."""

    duration_ms: int
    rgba_bytes: bytes
    color_table: tuple[tuple[int, int, int], ...]
    color_table_source: Literal["global", "local"]
    transparent_color_index: int | None
    disposal_method: int
    rectangle: tuple[int, int, int, int]


@dataclass(frozen=True)
class DecodedGif:
    """Absent loop extensions remain None; encoded zero remains zero."""

    width: int
    height: int
    loop_count: int | None
    frames: tuple[DecodedGifFrame, ...]
    global_color_table: tuple[tuple[int, int, int], ...]
    background_color_index: int
    application_extensions: tuple[tuple[bytes, bytes], ...] = ()


SequencePngDecoder = Callable[[bytes], DecodedSequencePng]
GifDecoder = Callable[[bytes], DecodedGif]
