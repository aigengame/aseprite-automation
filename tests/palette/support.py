"""Public Palette operations against native Frame-based Palette Changes."""

import struct
import zlib
from pathlib import Path

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.support import inject_palette_change, process_diagnostics

FIXTURES = Path(__file__).parent / "fixtures"


def png_chunk(kind: bytes, data: bytes) -> bytes:
    """Encode a PNG fixture chunk with its length and CRC."""
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data))
    )


def oversized_palette_png() -> bytes:
    """Small malformed input with valid chunks and an oversized Indexed raster header."""

    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 14000, 14000, 8, 3, 0, 0, 0))
        + png_chunk(b"PLTE", bytes([10, 20, 30]))
        + png_chunk(b"IDAT", zlib.compress(b"\0\0"))
        + png_chunk(b"IEND", b"")
    )


def quantization_sprite(
    runtime: RuntimeObservation, source: Path, **params: object
) -> None:
    """Write the Color Quantization Sprite of `quantization.lua` to source."""
    lua = run_lua(FIXTURES / "quantization.lua", runtime, source=source, **params)
    assert lua.returncode == 0, process_diagnostics(lua)


def index_organization_sprite(
    runtime: RuntimeObservation, source: Path, **params: object
) -> None:
    """Write the Palette index organization Sprite of `index_organization.lua`."""
    lua = run_lua(FIXTURES / "index_organization.lua", runtime, source=source, **params)
    assert lua.returncode == 0, process_diagnostics(lua)


def palette_fixture(
    runtime: RuntimeObservation,
    source: Path,
    mode: str = "indexed",
    *,
    short_palette: bool = False,
) -> None:
    """Write the Sprite of `palette_changes.lua` to source.

    Then add native Palette Changes at Frames 3 and 5.
    """
    lua = run_lua(
        FIXTURES / "palette_changes.lua",
        runtime,
        source=source,
        mode=mode,
        short_palette=short_palette,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    for frame, color in [(3, (40, 80, 220, 255)), (5, (220, 100, 30, 255))]:
        inject_palette_change(
            source,
            [(10, 20, 30, 255), color, (20, 200, 40, 128), (50, 60, 70, 0)],
            frame_number=frame,
        )
