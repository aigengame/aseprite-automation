"""Independent complete GIF block and logical-screen frame observations."""

import struct
from dataclasses import replace
from io import BytesIO
from typing import Literal

from PIL import Image, UnidentifiedImageError

from spa.contracts.encoded_animation import (
    AnimationDecodeError,
    DecodedGif,
    DecodedGifFrame,
)


class _Blocks:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

    def read(self, count: int) -> bytes:
        if count > len(self.payload) - self.offset:
            raise ValueError("Truncated GIF block")
        result = self.payload[self.offset : self.offset + count]
        self.offset += count
        return result

    def byte(self) -> int:
        return self.read(1)[0]

    def subblocks(self) -> tuple[bytes, ...]:
        blocks: list[bytes] = []
        while size := self.byte():
            blocks.append(self.read(size))
        return tuple(blocks)

    def table(self, packed: int) -> tuple[tuple[int, int, int], ...]:
        data = self.read(3 * 2 ** ((packed & 7) + 1))
        return tuple(
            (data[at], data[at + 1], data[at + 2]) for at in range(0, len(data), 3)
        )


def _encoded(payload: bytes) -> DecodedGif:
    blocks = _Blocks(payload)
    if blocks.read(6) not in (b"GIF87a", b"GIF89a"):
        raise ValueError("GIF signature is absent")
    width, height, packed, background, _aspect = struct.unpack("<HHBBB", blocks.read(7))
    if width == 0 or height == 0:
        raise ValueError("Invalid GIF logical screen dimensions")
    global_table = blocks.table(packed) if packed & 128 else ()
    if global_table and background >= len(global_table):
        raise ValueError("GIF Background Color Index exceeds global color table")
    frames: list[DecodedGifFrame] = []
    loop_count: int | None = None
    extensions: list[tuple[bytes, bytes]] = []
    control: tuple[int, int, int | None] | None = None
    while True:
        marker = blocks.byte()
        if marker == 0x3B:
            if blocks.offset != len(payload) or not frames or control is not None:
                raise ValueError("Invalid GIF trailer or incomplete Frame set")
            return DecodedGif(
                width,
                height,
                loop_count,
                tuple(frames),
                global_table,
                background,
                tuple(extensions),
            )
        if marker == 0x21:
            extension = blocks.byte()
            if extension == 0xF9:
                if blocks.byte() != 4 or control is not None:
                    raise ValueError(
                        "Invalid or duplicate GIF Graphics Control Extension"
                    )
                flags, delay, index = struct.unpack("<BHB", blocks.read(4))
                disposal = (flags >> 2) & 7
                if flags & 0xE0 or disposal > 3 or blocks.byte() != 0:
                    raise ValueError("Invalid GIF Graphics Control Extension")
                control = (delay * 10, disposal, index if flags & 1 else None)
            elif extension == 0xFF:
                if blocks.byte() != 11:
                    raise ValueError("Invalid GIF Application Extension")
                identifier = blocks.read(11)
                data = blocks.subblocks()
                extensions.append((identifier, b"".join(data)))
                if identifier in (b"NETSCAPE2.0", b"ANIMEXTS1.0"):
                    if (
                        loop_count is not None
                        or len(data) != 1
                        or len(data[0]) != 3
                        or data[0][0] != 1
                    ):
                        raise ValueError("Invalid or duplicate GIF loop extension")
                    loop_count = struct.unpack("<H", data[0][1:])[0]
            elif extension == 0xFE:
                blocks.subblocks()
            else:
                raise ValueError("Unsupported GIF Extension")
            continue
        if marker != 0x2C:
            raise ValueError("Invalid GIF block marker")
        x, y, frame_width, frame_height, packed = struct.unpack(
            "<HHHHB", blocks.read(9)
        )
        if (
            packed & 0x18
            or frame_width == 0
            or frame_height == 0
            or x + frame_width > width
            or y + frame_height > height
        ):
            raise ValueError("Invalid GIF Image Descriptor")
        source: Literal["global", "local"] = "local" if packed & 128 else "global"
        table = blocks.table(packed) if source == "local" else global_table
        if not table:
            raise ValueError("GIF Image has no color table")
        duration, disposal, transparent = control or (0, 0, None)
        if transparent is not None and transparent >= len(table):
            raise ValueError("GIF Transparent Color Index exceeds color table")
        control = None
        if not 2 <= blocks.byte() <= 8:
            raise ValueError("Invalid GIF LZW minimum code size")
        if not blocks.subblocks():
            raise ValueError("GIF Image data is absent")
        frames.append(
            DecodedGifFrame(
                duration,
                b"",
                table,
                source,
                transparent,
                disposal,
                (x, y, frame_width, frame_height),
            )
        )


def decode_gif(payload: bytes) -> DecodedGif:
    """Observe encoded tables/timing and independently decode every displayed Frame."""
    try:
        encoded = _encoded(payload)
        frames: list[DecodedGifFrame] = []
        with Image.open(BytesIO(payload)) as image:
            if image.format != "GIF" or image.size != (encoded.width, encoded.height):
                raise ValueError("GIF decoder disagrees with logical screen")
            for index, frame in enumerate(encoded.frames):
                image.seek(index)
                image.load()
                if image.size != (encoded.width, encoded.height):
                    raise ValueError(
                        "GIF decoded Frame changed logical screen dimensions"
                    )
                frames.append(
                    replace(frame, rgba_bytes=image.convert("RGBA").tobytes())
                )
            try:
                image.seek(len(encoded.frames))
            except EOFError:
                pass
            else:
                raise ValueError("GIF decoder found an undeclared Frame")
        return replace(encoded, frames=tuple(frames))
    except (
        OSError,
        ValueError,
        SyntaxError,
        EOFError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        raise AnimationDecodeError(str(exc)) from exc
