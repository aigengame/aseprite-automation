"""Brightness/Contrast uses Aseprite's native Filter, then verifies persistence."""

import pytest

from tests.filter.support import (
    apply,
    native_script,
    observe_images,
    pixels,
    rgb_palette_colors,
    run,
)

pytestmark = pytest.mark.e2e


def test_surface_reports_observed_manual_tilemap_filter(runtime):
    code, manifest = run("info")
    assert code == 0, manifest
    assert "spa filter brightness-contrast" in manifest["supported_capabilities"]
    assert (
        "aseprite_filter_brightness_contrast_tilemap_manual"
        in manifest["runtime"]["verified_capabilities"]
    )
    assert not any(
        gap["capability"] == "spa filter brightness-contrast: Manual Tilemap pixels"
        for gap in manifest["capability_gaps"]
    )
    assert any(
        gap["capability"] == "spa filter hue-saturation: Tilemap pixels"
        for gap in manifest["capability_gaps"]
    )


@pytest.mark.parametrize(
    "mode,application",
    [
        ("rgb", pixels()),
        ("grayscale", pixels("grayscale")),
        ("indexed", pixels("indexed", palette_frame_number=1)),
        ("rgb", rgb_palette_colors()),
        (
            "indexed",
            {
                "kind": "indexed-palette-entries",
                "palette_frame_number": 1,
                "entries": {"kind": "all"},
                "channels": {"kind": "components", "names": ["red", "green", "blue"]},
            },
        ),
    ],
)
def test_explicit_zero_is_noop_without_requantizing_duplicate_colors(
    tmp_path, runtime, mode, application
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "noop.lua", source=source, mode=mode)
    before = observe_images(runtime, source)
    code, result = apply(source, target, application, brightness=0, contrast=0)
    assert code == 0, result
    assert observe_images(runtime, target) == before
    assert result["changed"] is False
    assert result["processed_image_numbers"] == []


def test_rgb_pixels_are_native_and_source_is_unchanged(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="rgb")
    before = source.read_bytes()
    code, result = apply(source, target, pixels())
    assert code == 0, result
    assert result["changed"] is True
    assert result["persisted_reopen_verified"] is True
    assert (result["brightness"], result["contrast"], result["application"]) == (
        50,
        0,
        "pixels",
    )
    assert result["cels_target_kind"] == "selected"
    assert result["selection"] == {
        "kind": "all",
        "rectangle": {"x": 0, "y": 0, "width": 3, "height": 1},
    }
    assert result["palette_indexes"] == []
    assert result["processed_image_numbers"] == [1]
    assert result["channels"] == {
        "kind": "components",
        "names": ["red", "green", "blue"],
    }
    assert len(result["images"]) == 1
    assert len(result["affected_cels"]) == 1
    assert source.read_bytes() == before
    native_script(runtime, "check_rgb.lua", source=target)


def test_grayscale_only_changes_gray_and_retains_alpha(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="grayscale")
    code, result = apply(source, target, pixels("grayscale"))
    assert code == 0, result
    native_script(runtime, "check_gray.lua", source=target)


def test_indexed_pixels_use_explicit_palette_without_changing_entries(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="indexed")
    code, result = apply(source, target, pixels("indexed", palette_frame_number=1))
    assert code == 0, result
    assert result["palette_before"] == result["palette_after"]
    assert result["palette_basis"]["palette_frame_number"] == 1
    native_script(runtime, "check_indexed_pixels.lua", source=target)


def test_indexed_palette_only_changes_explicit_entries_and_no_pixels(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="indexed")
    code, result = apply(
        source,
        target,
        {
            "kind": "indexed-palette-entries",
            "palette_frame_number": 1,
            "entries": {"kind": "selected", "indexes": [1]},
            "channels": {"kind": "components", "names": ["red"]},
        },
    )
    assert code == 0, result
    assert result["existing_target_cels"] == []
    assert result["cels_target_kind"] is None
    assert result["selection"] is None
    assert result["palette_indexes"] == [1]
    assert result["processed_image_numbers"] == []
    assert result["images"] == []
    assert result["changed"] is True
    native_script(runtime, "check_palette.lua", source=target, mode="indexed")


@pytest.mark.parametrize(
    "cels_target",
    [
        {"kind": "selected", "layers": [{"layer_path": [2]}], "frame_numbers": [1]},
        {
            "kind": "selected",
            "layers": [{"layer_path": [1]}, {"layer_path": [2]}],
            "frame_numbers": [1],
        },
        {"kind": "all"},
    ],
)
def test_tilemap_pixel_target_refuses_before_publication(
    tmp_path, runtime, cels_target
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="rgb")
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    application = pixels(cels_target=cels_target)
    code, result = apply(source, target, application, overwrite=True)
    assert code != 0 and result["code"] == "filter_unsupported_document", result
    assert "Tilemap" in result["details"]["reason"]
    assert source.read_bytes() == original
    assert target.read_bytes() == b"existing target"


def test_palette_only_uses_tilemap_anchor_and_preserves_every_image(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="indexed", only="true")
    before = observe_images(runtime, source)
    code, result = apply(
        source,
        target,
        {
            "kind": "indexed-palette-entries",
            "palette_frame_number": 1,
            "entries": {"kind": "selected", "indexes": [1]},
            "channels": {"kind": "components", "names": ["red"]},
        },
    )
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after["cels"] == before["cels"]
    assert after["tiles"] == before["tiles"]
    assert after["palette"][1] == [120, 40, 20, 100]
    assert result["images"] == [] and result["affected_cels"] == []


def test_indexed_native_quantization_can_change_alpha_without_filtering_tiles(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="indexed")
    before = observe_images(runtime, source)
    code, result = apply(
        source,
        target,
        pixels(
            "indexed",
            palette_frame_number=1,
            channels={"kind": "components", "names": ["red"]},
        ),
    )
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after["cels"][0]["pixels"][0] == 2
    assert before["palette"][1][3] == 100 and after["palette"][2][3] == 101
    assert after["palette"] == before["palette"]
    assert after["tiles"] == before["tiles"]
    assert after["cels"][1] == before["cels"][1]


def test_rgb_palette_colors_changes_only_exact_old_color_matches(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="rgb")
    code, result = apply(source, target, rgb_palette_colors())
    assert code == 0, result
    assert result["changed"] is True
    native_script(runtime, "check_palette.lua", source=target, mode="rgb")


@pytest.mark.parametrize("palette_colors", [False, True])
def test_empty_selection_keeps_images_but_retains_palette_application(
    tmp_path, runtime, palette_colors
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="rgb")
    before = observe_images(runtime, source)
    application = (rgb_palette_colors if palette_colors else pixels)(
        selection={"kind": "empty"}
    )
    code, result = apply(source, target, application)
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after["cels"] == before["cels"]
    assert result["changed"] is palette_colors
    assert after["palette"][1][0] == (150 if palette_colors else 100)
