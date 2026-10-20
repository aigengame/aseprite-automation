"""The shared Palette resolver observes native changes through its consumer Interface."""

import json
from importlib.resources import files
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.palette.support import FIXTURES
from tests.support import inject_palette_change, process_diagnostics

pytestmark = pytest.mark.e2e


def test_effective_palette_resolves_change_points_without_active_frame_state(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = tmp_path / "changes.aseprite"
    output = tmp_path / "observed.json"
    parameters = {
        "source": source,
        "out": output,
        "effective_palette": files("spa.kernel").joinpath(
            "color/effective_palette.lua"
        ),
    }
    script = FIXTURES / "effective_palette.lua"

    lua = run_lua(script, runtime, mode="create", **parameters)
    assert lua.returncode == 0, process_diagnostics(lua)
    inject_palette_change(source, [(0, 0, 0, 0), (20, 40, 200, 255)], frame_number=3)
    original = source.read_bytes()

    lua = run_lua(script, runtime, mode="observe", **parameters)
    assert lua.returncode == 0, process_diagnostics(lua)

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
