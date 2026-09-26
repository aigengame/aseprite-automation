"""One complete fresh hybrid build matches retained exports and native sources."""

import json
import os
from pathlib import Path

import pytest

from examples.wizard_cast_v2.build import build
from examples.wizard_cast_v2.native_inspection import compare_native
from examples.wizard_cast_v2.verify import compare_delivery
from examples.wizard_cast_v2.workflow import Spa

pytestmark = [pytest.mark.e2e, pytest.mark.slow]
EXAMPLE = Path(__file__).resolve().parents[2] / "examples/wizard_cast_v2"


def test_complete_hybrid_recipe_reproduces_delivery(tmp_path: Path) -> None:
    cli = os.environ.get("SPA_TEST_INSTALLED_CLI", str(Path(".venv/bin/spa").resolve()))
    aseprite = os.environ["SPA_TEST_ASEPRITE"]
    fresh = tmp_path / "fresh"
    build(cli, aseprite, fresh)
    compare_delivery(fresh, EXAMPLE / "godot/content/wizard_assets")
    spa = Spa(cli, aseprite, fresh / "evidence/delivery-inspection.jsonl")
    palette = {
        color.lower()
        for color in json.loads((fresh / "recipe.json").read_text())["palette"].values()
    }
    generated_sources = sorted((fresh / "source").glob("*.aseprite"))
    assert len(generated_sources) == 7
    assert {path.name for path in generated_sources} == {
        path.name for path in (EXAMPLE / "source").glob("*.aseprite")
    }
    for source in generated_sources:
        compare_native(source, EXAMPLE / "source" / source.name, spa, tmp_path, palette)
