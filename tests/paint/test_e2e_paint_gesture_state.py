"""Same-process state and publication checks for native Paint gestures."""

import os
import subprocess
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.authoring.raster.paint_native import NATIVE_PAINT_RESOURCES
from spa.contracts.public import RuntimeRequest

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("tool", ["contour", "blur"])
def test_gesture_restores_invocation_state_and_preserves_files(
    tmp_path: Path, tool: str
) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    workspace = tmp_path / "isolation"
    workspace.mkdir()
    prepared = prepare_invocation(
        Path(observation.canonical_path), Path(observation.resource_path), workspace
    )
    blocked_parent = tmp_path / "blocked-stage-parent"
    blocked_parent.write_bytes(b"not a directory")
    kernel = Path(__file__).parents[2] / "src" / "spa" / "kernel"
    params = {
        "tool": tool,
        "source": str(tmp_path / "source.aseprite"),
        "target": str(tmp_path / "painted.aseprite"),
        "failure": str(tmp_path / "failure.aseprite"),
        "midway": str(tmp_path / "midway.aseprite"),
        "unwritable": str(blocked_parent / "painted.aseprite"),
    }
    for resource in NATIVE_PAINT_RESOURCES:
        params[resource.parameter_name] = str(kernel / resource.package_name)
    args = [str(prepared.executable), "--batch"]
    for name, value in params.items():
        args.extend(("--script-param", f"{name}={value}"))
    args.extend(
        (
            "--script",
            str(Path(__file__).parent / "fixtures" / "paint_gesture_isolation.lua"),
        )
    )
    run = subprocess.run(
        args, text=True, capture_output=True, env=prepared.environment, check=False
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert Path(params["source"]).is_file()
    assert Path(params["target"]).is_file()
    assert not Path(params["failure"]).exists()
    assert not Path(params["midway"]).exists()
