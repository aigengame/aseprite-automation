"""Application boundaries retain native Alpha, Palette, and addressing semantics."""

import pytest

from tests.filter.support import (
    apply,
    native_script,
    observe_images,
    pixels,
    rgb_palette_colors,
)

pytestmark = pytest.mark.e2e


def test_rgb_palette_matching_includes_alpha(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "boundary.lua", source=source)
    before = observe_images(runtime, source)
    code, result = apply(source, target, rgb_palette_colors())
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after["cels"][0]["pixels"][0] == (100 << 24 | 20 << 16 | 40 << 8 | 120)
    assert after["cels"][0]["pixels"][1] == before["cels"][0]["pixels"][1]
    assert after["palette"][1] == [120, 40, 20, 100]


def test_background_accepts_green_blue_and_preserves_red_alpha(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "boundary.lua", source=source, background="true")
    code, result = apply(
        source,
        target,
        pixels(channels={"kind": "components", "names": ["blue", "green"]}),
    )
    assert code == 0, result
    assert result["channels"]["names"] == ["green", "blue"]
    assert (
        observe_images(runtime, target)["cels"][0]["pixels"]
        == [255 << 24 | 30 << 16 | 60 << 8 | 80] * 2
    )


def test_palette_all_reports_every_entry_and_preserves_all_images(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="indexed")
    before = observe_images(runtime, source)
    code, result = apply(
        source,
        target,
        {
            "kind": "indexed-palette-entries",
            "palette_frame_number": 1,
            "entries": {"kind": "all"},
            "channels": {"kind": "components", "names": ["red"]},
        },
    )
    assert code == 0, result
    after = observe_images(runtime, target)
    assert result["palette_indexes"] == list(range(len(before["palette"])))
    assert after["cels"] == before["cels"] and after["tiles"] == before["tiles"]
    assert [color[0] for color in after["palette"]] == [0, 120, 180]
    assert [color[3] for color in after["palette"]] == [
        color[3] for color in before["palette"]
    ]


@pytest.mark.parametrize(
    "options",
    [
        {"palette_frame_number": 2},
        {"indexes": [99]},
        {
            "cels_target": {
                "kind": "selected",
                "layers": [{"layer_path": [1]}, {"layer_name": "Layer 1"}],
                "frame_numbers": [1],
            }
        },
    ],
)
def test_native_address_refusal_preserves_source_and_existing_target(
    tmp_path, runtime, options
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "boundary.lua", source=source)
    before = source.read_bytes()
    target.write_bytes(b"existing target")
    code, result = apply(source, target, rgb_palette_colors(**options), overwrite=True)
    assert code == 2 and result["code"] == "filter_invalid_target", result
    assert source.read_bytes() == before
    assert target.read_bytes() == b"existing target"
