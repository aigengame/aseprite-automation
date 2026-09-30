"""Missing shared Document bindings fail before native dofile receives nil."""

from importlib.resources import files
from pathlib import Path

import pytest

from tests.frame.test_e2e_frame import _run_fixture

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
    consumer: str, missing: str
) -> None:
    _run_fixture(
        str(Path(__file__).parent / "fixtures" / "missing_document_resource.lua"),
        consumer=str(files("spa.kernel").joinpath(consumer)),
        missing=missing,
    )
