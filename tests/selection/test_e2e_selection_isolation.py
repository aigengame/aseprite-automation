"""Real native Selection operations preserve the caller and release temporary state."""

import json
from importlib.resources import files
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("scenario", ["success", "failure"])
def test_selection_kernel_preserves_caller_and_closes_temporary_sprites(
    tmp_path: Path, runtime: RuntimeObservation, scenario: str
) -> None:
    kernel = files("spa.kernel")
    source = tmp_path / "caller.aseprite"
    original = tmp_path / "original.aseprite"
    report = tmp_path / "isolation.json"
    lua = run_lua(
        Path(__file__).parent / "fixtures/selection_isolation.lua",
        runtime,
        selection_support=kernel.joinpath("raster/selection/selection_support.lua"),
        selection_mask=kernel.joinpath("raster/selection/selection_mask.lua"),
        source=source,
        original=original,
        out=report,
        scenario=scenario,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
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
