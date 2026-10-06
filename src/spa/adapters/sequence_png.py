"""Independent native-representation observations of sequence PNG bytes."""

import struct
import zlib
from io import BytesIO
from typing import Literal

from PIL import Image, UnidentifiedImageError

from spa.adapters.png_input import (
    _encoded_chunks,
    _entries,
    _profile,
    _verify_pixel_stream,
)
from spa.contracts.encoded_animation import AnimationDecodeError, DecodedSequencePng


def decode_sequence_png(payload: bytes) -> DecodedSequencePng:
    """Decode supported PNG samples without defining source or export policy."""
    try:
        chunks = _encoded_chunks(payload)
        if len(chunks.get(b"IHDR", b"")) != 13:
            raise ValueError("Invalid PNG IHDR")
        width, height, depth, color_type, compression, filtering, interlace = (
            struct.unpack(">IIBBBBB", chunks[b"IHDR"])
        )
        if not 0 < width <= 0x7FFFFFFF or not 0 < height <= 0x7FFFFFFF:
            raise ValueError("Invalid PNG dimensions")
        if color_type not in (0, 2, 3, 4, 6) or (
            depth not in (1, 2, 4, 8) if color_type == 3 else depth != 8
        ):
            raise ValueError(
                "PNG requires 8-bit channels or 1/2/4/8-bit Palette Indexes"
            )
        if compression != 0 or filtering != 0 or interlace not in (0, 1):
            raise ValueError("Unsupported PNG encoding method")
        if color_type in (0, 4):
            if b"PLTE" in chunks:
                raise ValueError("Grayscale PNG cannot contain PLTE")
            alpha = chunks.get(b"tRNS")
            if alpha is not None and (
                color_type != 0
                or len(alpha) != 2
                or struct.unpack(">H", alpha)[0] > 255
            ):
                raise ValueError("Invalid Grayscale PNG tRNS")
            entries = ()
        else:
            entries = _entries(chunks, color_type)
        if color_type == 3 and len(entries) > 2**depth:
            raise ValueError("PNG PLTE exceeds bit depth")
        profile, icc = _profile(chunks)
        with Image.open(BytesIO(payload)) as image:
            expected_mode = {0: "L", 2: "RGB", 3: "P", 4: "LA", 6: "RGBA"}[color_type]
            if (
                image.format != "PNG"
                or image.mode != expected_mode
                or image.size != (width, height)
            ):
                raise ValueError(
                    "PNG decoder representation disagrees with encoded facts"
                )
            _verify_pixel_stream(
                chunks[b"IDAT"], width, height, color_type, interlace, bit_depth=depth
            )
            image.load()
            mode: Literal["rgb", "grayscale", "indexed"]
            rgba = image.convert("RGBA").tobytes()
            if color_type == 3:
                mode, stored = "indexed", image.tobytes()
                if any(index >= len(entries) for index in stored):
                    raise ValueError("PNG pixel index exceeds PLTE")
            elif color_type in (0, 4):
                mode, stored = "grayscale", image.convert("LA").tobytes()
            else:
                mode, stored = "rgb", rgba
            return DecodedSequencePng(
                width,
                height,
                mode,
                color_type,
                depth,
                stored,
                rgba,
                entries,
                profile,
                icc,
                chunks[b"sRGB"][0] if b"sRGB" in chunks else None,
            )
    except (
        OSError,
        ValueError,
        SyntaxError,
        zlib.error,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        raise AnimationDecodeError(str(exc)) from exc
