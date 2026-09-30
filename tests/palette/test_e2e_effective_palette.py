"""The shared Palette resolver observes native changes through its consumer Interface."""

import json
import os
import subprocess
import tempfile
from importlib.resources import files
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import inject_palette_change, process_diagnostics

pytestmark = pytest.mark.e2e


def test_effective_palette_resolves_change_points_without_active_frame_state(
    tmp_path: Path,
) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    source = tmp_path / "changes.aseprite"
    output = tmp_path / "observed.json"

    def run_fixture(mode: str) -> None:
        with tempfile.TemporaryDirectory(prefix="spa-palette-fixture-") as work:
            prepared = prepare_invocation(
                Path(observation.canonical_path),
                Path(observation.resource_path),
                Path(work),
            )
            arguments = [str(prepared.executable), "--batch"]
            for key, value in {
                "mode": mode,
                "source": source,
                "out": output,
                "effective_palette": files("spa.kernel").joinpath(
                    "color/effective_palette.lua"
                ),
            }.items():
                arguments.extend(("--script-param", f"{key}={value}"))
            arguments.extend(
                (
                    "--script",
                    str(Path(__file__).parent / "fixtures" / "effective_palette.lua"),
                )
            )
            run = subprocess.run(
                arguments,
                text=True,
                capture_output=True,
                check=False,
                env=prepared.environment,
            )
        assert run.returncode == 0, process_diagnostics(run)

    run_fixture("create")
    inject_palette_change(source, [(0, 0, 0, 0), (20, 40, 200, 255)], frame_number=3)
    original = source.read_bytes()

    run_fixture("observe")

    result = json.loads(output.read_text())
    assert [
        (
            fact["requested_frame_number"],
            fact["palette_frame_number"],
            fact["native_frame_number"],
            fact["color"],
        )
        for fact in result["observations"]
    ] == [
        (5, 3, 3, [20, 40, 200, 255]),
        (1, 1, 1, [241, 82, 65, 255]),
        (2, 1, 1, [241, 82, 65, 255]),
        (3, 3, 3, [20, 40, 200, 255]),
        (4, 3, 3, [20, 40, 200, 255]),
    ]
    assert result["active_context_preserved"] is True
    assert source.read_bytes() == original
