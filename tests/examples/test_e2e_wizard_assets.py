"""The complete installed-SPA recipe, independent pixels, and reproducibility."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from examples.wizard_cast.build import build
from examples.wizard_cast.verify import compare_builds
from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation

pytestmark = pytest.mark.e2e


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


def test_complete_wizard_recipe_has_repeatable_saved_structure_and_pixels(
    tmp_path: Path,
) -> None:
    cli = os.environ.get("SPA_TEST_INSTALLED_CLI", str(Path(".venv/bin/spa").resolve()))
    aseprite = os.environ["SPA_TEST_ASEPRITE"]
    first, second = tmp_path / "first", tmp_path / "second"
    build(cli, aseprite, first)
    build(cli, aseprite, second)
    result = compare_builds(first, second)
    assert result["frame_count"] == 32
    native = inspect_stored_pixels(
        first / "source/wizard_scene.aseprite", aseprite, first / "evidence/native.json"
    )
    recipe = json.loads((first / "recipe.json").read_text())
    assert set(native["stored_colors"]) <= {
        color.lower() for color in recipe["palette"].values()
    }
