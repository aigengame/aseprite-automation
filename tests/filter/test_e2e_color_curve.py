"""Color Curve is executed by Aseprite and verified after reopening the Target."""

import pytest

from tests.filter.support import native_script, observe_images, pixels, run

pytestmark = pytest.mark.e2e


def test_constant_red_curve_preserves_other_components_and_source(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="rgb")
    original = source.read_bytes()
    options = pixels(channels={"kind": "components", "names": ["red"]})
    options.pop("kind")
    code, result = run(
        "filter",
        "color-curve",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        points=[{"input": 100, "output": 42}],
        **options,
    )
    assert code == 0, result
    assert result["changed"] is True
    assert result["persisted_reopen_verified"] is True
    after = observe_images(runtime, target)
    assert after["cels"][0]["pixels"] == [
        42 | (60 << 8) | (20 << 16) | (255 << 24),
        42 | (100 << 8) | (40 << 16) | (128 << 24),
        42 | (20 << 8) | (10 << 16) | (255 << 24),
    ]
    assert source.read_bytes() == original
