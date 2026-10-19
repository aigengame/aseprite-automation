"""Same-process state and publication checks for native Paint gestures."""

from importlib.resources import files
from pathlib import Path

import pytest

from spa.authoring.raster.paint_native import NATIVE_PAINT_RESOURCES
from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.paint.support import FIXTURES
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("tool", ["contour", "blur"])
def test_gesture_restores_invocation_state_and_preserves_files(
    runtime: RuntimeObservation, tmp_path: Path, tool: str
) -> None:
    blocked_parent = tmp_path / "blocked-stage-parent"
    blocked_parent.write_bytes(b"not a directory")
    kernel = files("spa.kernel")
    params = {
        "tool": tool,
        "source": str(tmp_path / "source.aseprite"),
        "target": str(tmp_path / "painted.aseprite"),
        "failure": str(tmp_path / "failure.aseprite"),
        "midway": str(tmp_path / "midway.aseprite"),
        "unwritable": str(blocked_parent / "painted.aseprite"),
    }
    for resource in NATIVE_PAINT_RESOURCES:
        params[resource.parameter_name] = str(kernel.joinpath(resource.package_path))
    lua = run_lua(FIXTURES / "paint_gesture_isolation.lua", runtime, **params)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert Path(params["source"]).is_file()
    assert Path(params["target"]).is_file()
    assert not Path(params["failure"]).exists()
    assert not Path(params["midway"]).exists()
