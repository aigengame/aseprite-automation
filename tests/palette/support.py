"""Public Palette operations against native Frame-based Palette Changes."""

import json
import os
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

from spa.adapters.aseprite.invocation import prepare_invocation
from tests.support import inject_palette_change, process_diagnostics, spa


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


def run_palette(*command: str, **request: object) -> tuple[int, dict]:
    result = spa(
        *command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


def native_script(runtime, name: str, **params: object) -> None:
    with tempfile.TemporaryDirectory(prefix="spa-palette-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                *[
                    part
                    for key, value in params.items()
                    for part in ("--script-param", f"{key}={value}")
                ],
                "--script",
                str(Path(__file__).parent / "fixtures" / name),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, process_diagnostics(run)


def palette_fixture(
    source: Path, runtime, mode: str = "indexed", *, short_palette: bool = False
) -> None:
    native_script(
        runtime,
        "palette_changes.lua",
        source=source,
        mode=mode,
        short_palette=str(short_palette).lower(),
    )
    for frame, color in [(3, (40, 80, 220, 255)), (5, (220, 100, 30, 255))]:
        inject_palette_change(
            source,
            [(10, 20, 30, 255), color, (20, 200, 40, 128), (50, 60, 70, 0)],
            frame_number=frame,
        )
