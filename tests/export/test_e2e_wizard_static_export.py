"""One retained wizard component exported from its unchanged scene Source."""

import json
from pathlib import Path

import pytest
from PIL import Image

from tests.export.test_e2e_static_geometry import _export, _request

pytestmark = pytest.mark.e2e
EXAMPLE = Path(__file__).resolve().parents[2] / "examples/wizard_cast_v2"


def test_retained_wizard_scene_exports_gem_component_without_authoring_copy(
    tmp_path: Path,
) -> None:
    source = EXAMPLE / "source/wizard_scene.aseprite"
    before = source.read_bytes()
    assert not before.startswith(b"version https://git-lfs.github.com/spec/v1"), (
        "This retained-asset test requires Git LFS content"
    )
    definition = json.loads((EXAMPLE / "recipe.json").read_text())["export"][
        "components"
    ]["gem"]
    destination = tmp_path / "gem.png"
    # Frame 1 has no camera shake or pulse. Its gem world position already equals
    # the component recipe's local position, so export needs no motion edit.
    result = _export(
        _request(
            source,
            destination,
            frame_number=1,
            export_image_area={"kind": "rectangle", "rectangle": definition["crop"]},
            layer_composition={"mode": "include", "layers": [{"layer_name": "gem"}]},
        )
    )
    assert result["export_image_area"]["rectangle"] == definition["crop"]
    assert result["resolved_layer_paths"] == [[4]]
    with (
        Image.open(destination) as actual,
        Image.open(EXAMPLE / "godot/content/wizard_assets/gem/0001.png") as expected,
    ):
        assert actual.size == expected.size == (104, 116)
        assert actual.mode == "RGBA"
        assert actual.getbbox() is not None
        assert actual.convert("RGBA").tobytes() == expected.convert("RGBA").tobytes()
    assert source.read_bytes() == before
