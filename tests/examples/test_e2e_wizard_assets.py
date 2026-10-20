"""The complete installed-SPA recipe, independent pixels, and reproducibility."""

import json
import os
from pathlib import Path

import pytest

from examples.wizard_cast.build import build
from examples.wizard_cast.verify import compare_delivery, inspect_build
from examples.wizard_cast.workflow import Spa
from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.support import installed_cli, process_diagnostics

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def inspect_stored_pixels(
    source: Path, runtime: RuntimeObservation, output: Path
) -> dict:
    """Read the stored pixels of source with `inspect_wizard.lua` into output.

    It also asserts binary alpha, integer positions and an sRGB or absent profile.
    """
    lua = run_lua(
        Path(__file__).with_name("inspect_wizard.lua"),
        runtime,
        source=source,
        out=output,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    result = json.loads(output.read_text())
    assert result["nonbinary_alpha"] == 0
    assert result["noninteger_positions"] == 0
    assert result["srgb"] or result["no_profile"]
    return result


def test_complete_wizard_recipe_reproduces_delivered_structure_and_pixels(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    cli = installed_cli()
    aseprite = os.environ["SPA_TEST_ASEPRITE"]
    first = tmp_path / "fresh"
    build(cli, aseprite, first)
    example = Path(__file__).resolve().parents[2] / "examples/wizard_cast"
    compare_delivery(first, example / "godot/content/wizard_assets")
    generated = inspect_build(first)["sprite"]
    assert generated["metadata"]["frame_count"] == 32
    retained = Spa(cli, aseprite, first / "evidence/delivery-inspection.jsonl").call(
        "sprite get",
        sprite_file=str(example / "source/wizard_scene.aseprite"),
        inspection_scope=["frames", "layers", "cels", "tags"],
    )
    assert generated == {key: retained[key] for key in generated}
    native = inspect_stored_pixels(
        first / "source/wizard_scene.aseprite", runtime, first / "evidence/native.json"
    )
    recipe = json.loads((first / "recipe.json").read_text())
    assert set(native["stored_colors"]) <= {
        color.lower() for color in recipe["palette"].values()
    }
