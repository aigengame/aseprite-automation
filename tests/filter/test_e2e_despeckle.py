"""Native Despeckle through the public Filter surface."""

import pytest

from tests.filter.support import native_script, observe_images, pixels, run

pytestmark = pytest.mark.e2e


def pixel_input(mode="rgb", **options):
    selected = pixels(mode, **options)
    del selected["kind"]
    return selected


def apply(source, target, selected, width=3, height=1, tiled_mode="none", **intent):
    return run(
        "filter",
        "despeckle",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=intent.pop("in_place", False),
        overwrite=intent.pop("overwrite", False),
        pixels=selected,
        width=width,
        height=height,
        tiled_mode=tiled_mode,
        **intent,
    )


def test_despeckle_uses_native_median_and_verifies_persistence(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="grayscale")
    original = source.read_bytes()
    code, result = apply(source, target, pixel_input("grayscale"))
    assert code == 0, result
    assert result["anchor"] == {"x": 1, "y": 0}
    assert result["sample_count"] == 3
    assert result["persisted_reopen_verified"] is True
    assert result["processed_image_numbers"] == [1]
    assert result["changed"] is True
    observed = observe_images(runtime, target)
    assert [value & 255 for value in observed["cels"][0]["pixels"]] == [100, 100, 40]
    assert source.read_bytes() == original
