"""Native Source Sprite fixtures for delivery E2E tests."""

import os
import subprocess
import tempfile
from pathlib import Path

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import process_diagnostics


def source_sprite(
    tmp_path: Path,
    fixture_name: str = "rgb_frames.lua",
    **params: str,
) -> Path:
    source = tmp_path / "source.aseprite"
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]),
        PROBE_RESOURCES,
    )
    fixture = Path(__file__).parent / "fixtures" / fixture_name
    with tempfile.TemporaryDirectory(prefix="spa-export-fixture-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={source}",
                *[
                    argument
                    for name, value in params.items()
                    for argument in ("--script-param", f"{name}={value}")
                ],
                "--script",
                str(fixture),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, process_diagnostics(run)
    assert source.is_file()
    return source
