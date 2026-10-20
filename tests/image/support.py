"""Independent native observations of Image results."""

import json
from pathlib import Path

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.support import process_diagnostics


def inspect_native(
    runtime: RuntimeObservation,
    source: Path,
    tmp_path: Path,
    x: int,
    y: int,
    frame_number: int = 1,
    *,
    row: bool = False,
) -> dict:
    """Return the pixel at x, y of frame_number that `inspect_image.lua` reads.

    With row, the result also has the pixels of row y. The fixture writes
    `pixel-<frame>-<x>-<y>.json` in tmp_path.
    """
    output = tmp_path / f"pixel-{frame_number}-{x}-{y}.json"
    lua = run_lua(
        Path(__file__).parent / "fixtures" / "inspect_image.lua",
        runtime,
        source=source,
        frame=frame_number,
        x=x,
        y=y,
        out=output,
        row=row,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    return json.loads(output.read_text())
