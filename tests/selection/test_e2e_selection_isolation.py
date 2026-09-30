"""Real native Selection operations preserve the caller and release temporary state."""

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
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("scenario", ["success", "failure"])
def test_selection_kernel_preserves_caller_and_closes_temporary_sprites(
    tmp_path: Path, scenario: str
) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    kernel = files("spa.kernel")
    source = tmp_path / "caller.aseprite"
    original = tmp_path / "original.aseprite"
    report = tmp_path / "isolation.json"
    with tempfile.TemporaryDirectory(prefix="spa-selection-isolation-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        args = [str(prepared.executable), "--batch"]
        for key, value in {
            "selection_support": kernel.joinpath(
                "raster/selection/selection_support.lua"
            ),
            "selection_mask": kernel.joinpath("raster/selection/selection_mask.lua"),
            "source": source,
            "original": original,
            "out": report,
            "scenario": scenario,
        }.items():
            args.extend(("--script-param", f"{key}={value}"))
        args.extend(
            (
                "--script",
                str(Path(__file__).parent / "fixtures/selection_isolation.lua"),
            )
        )
        run = subprocess.run(
            args,
            capture_output=True,
            text=True,
            env=prepared.environment,
            check=False,
            timeout=45,
        )
    assert run.returncode == 0, process_diagnostics(run)
    assert source.read_bytes() == original.read_bytes()
    assert json.loads(report.read_text()) == {
        "checked": (
            ["ellipse", "grow", "shrink", "flip", "rotate", "scale"]
            if scenario == "success"
            else ["native_parameter_failure", "failure_without_caller"]
        ),
        "caller_preserved": True,
        "temporary_sprites_closed": True,
    }
