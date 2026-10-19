"""Native Color Quantization restores temporary editor state."""

from importlib.resources import files

import pytest

from spa.authoring.color.quantization import PALETTE_QUANTIZATION_HANDLER
from tests.native_invocation import run_lua
from tests.palette.support import FIXTURES
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


def test_shared_quantization_restores_editor_state_on_success_and_failure(runtime):
    lua = run_lua(
        FIXTURES / "quantization_state.lua",
        runtime,
        **{
            resource.parameter_name: str(
                files("spa.kernel").joinpath(resource.package_path)
            )
            for resource in PALETTE_QUANTIZATION_HANDLER.support_resources
        },
    )
    assert lua.returncode == 0, process_diagnostics(lua)
