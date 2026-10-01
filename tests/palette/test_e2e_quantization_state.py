"""Native Color Quantization restores temporary editor state."""

from importlib.resources import files

import pytest

from spa.authoring.color.quantization import PALETTE_QUANTIZATION_HANDLER
from tests.palette.support import native_script

pytestmark = pytest.mark.e2e


def test_shared_quantization_restores_editor_state_on_success_and_failure(runtime):
    native_script(
        runtime,
        "quantization_state.lua",
        **{
            resource.parameter_name: str(
                files("spa.kernel").joinpath(resource.package_path)
            )
            for resource in PALETTE_QUANTIZATION_HANDLER.support_resources
        },
    )
