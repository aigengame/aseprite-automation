"""Missing shared Document bindings fail before native dofile receives nil."""

from importlib.resources import files
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize(
    ("consumer", "missing"),
    [
        ("document/cel/cel_support.lua", "layer_select"),
        ("document/frame/frame_support.lua", "layer_select"),
        ("document/sprite/sprite_inspect.lua", "layer_select"),
        ("raster/paint/paint_apply_support.lua", "layer_select"),
        ("raster/paint/native_tool.lua", "layer_select"),
        ("document/animation/animation_support.lua", "cel"),
        ("document/layer/layer_mutation_support.lua", "cel"),
    ],
)
def test_missing_document_dependency_reports_lua_error(
    runtime: RuntimeObservation, consumer: str, missing: str
) -> None:
    # The fixture exits 0 only when loading fails with the expected message.
    lua = run_lua(
        Path(__file__).parent / "fixtures" / "missing_document_resource.lua",
        runtime,
        consumer=files("spa.kernel").joinpath(consumer),
        missing=missing,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
