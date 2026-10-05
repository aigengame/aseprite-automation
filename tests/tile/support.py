"""Native Tile fixtures and public CLI invocation."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from spa.adapters.aseprite.invocation import prepare_invocation
from tests.support import process_diagnostics, spa


def run(*command: str, **request: object) -> tuple[int, dict]:
    result = spa(
        *command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


def fixture(
    source: Path, runtime, *, script: str = "tiles.lua", **params: object
) -> None:
    with tempfile.TemporaryDirectory(prefix="spa-tile-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        result = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                *[
                    part
                    for key, value in {"source": source, **params}.items()
                    for part in ("--script-param", f"{key}={value}")
                ],
                "--script",
                str(Path(__file__).parent / "fixtures" / script),
            ],
            check=False,
            text=True,
            capture_output=True,
            env=prepared.environment,
        )
    assert result.returncode == 0, process_diagnostics(result)
    assert "Error" not in result.stdout + result.stderr, process_diagnostics(result)


def snapshot(mode: str = "rgb", *, transparent: bool = False) -> dict:
    color = {
        "rgb": {
            "kind": "rgba",
            "red": 0 if transparent else 17,
            "green": 0 if transparent else 29,
            "blue": 0 if transparent else 41,
            "alpha": 0 if transparent else 255,
        },
        "grayscale": {
            "kind": "grayscale",
            "gray": 0 if transparent else 79,
            "alpha": 0 if transparent else 255,
        },
        "indexed": {"kind": "palette-index", "index": 7 if transparent else 2},
    }[mode]
    return {
        "coordinate_space": "image-pixel",
        "color_mode": mode,
        "rectangle": {"x": 0, "y": 0, "width": 2, "height": 3},
        "rows": [[{"length": 2, "color": color}] for _ in range(3)],
    }
