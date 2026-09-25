"""The complete installed-SPA recipe, independent pixels, and reproducibility."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from examples.wizard_cast.build import build
from examples.wizard_cast.verify import compare_delivery, inspect_build
from examples.wizard_cast.workflow import Spa
from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def inspect_stored_pixels(source: Path, aseprite: str, output: Path) -> dict:
    observation = probe(RuntimeRequest(aseprite=aseprite), PROBE_RESOURCES)
    with tempfile.TemporaryDirectory(prefix="spa-wizard-inspect-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"source={source}",
                "--script-param",
                f"out={output}",
                "--script",
                str(Path(__file__).with_name("inspect_wizard.lua")),
            ],
            env=prepared.environment,
            capture_output=True,
            text=True,
            check=False,
        )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(output.read_text())
    assert result["nonbinary_alpha"] == 0
    assert result["noninteger_positions"] == 0
    assert result["srgb"] or result["no_profile"]
    return result


def test_complete_wizard_recipe_reproduces_delivered_structure_and_pixels(
    tmp_path: Path,
) -> None:
    cli = os.environ.get("SPA_TEST_INSTALLED_CLI", str(Path(".venv/bin/spa").resolve()))
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
        first / "source/wizard_scene.aseprite", aseprite, first / "evidence/native.json"
    )
    recipe = json.loads((first / "recipe.json").read_text())
    assert set(native["stored_colors"]) <= {
        color.lower() for color in recipe["palette"].values()
    }
