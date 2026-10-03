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


def fixture(source: Path, runtime, **params: object) -> None:
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
                str(Path(__file__).parent / "fixtures" / "tiles.lua"),
            ],
            check=False,
            text=True,
            capture_output=True,
            env=prepared.environment,
        )
    assert result.returncode == 0, process_diagnostics(result)
