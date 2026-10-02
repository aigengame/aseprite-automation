"""Fixed-pixel Filters keep shared target, selection, and native writeback rules."""

import pytest

from tests.filter.support import native_script, observe_images, pixels, run

pytestmark = pytest.mark.e2e


def apply_filter(
    name, source, target, *, mode="rgb", channel="red", value=0, **options
):
    fields = pixels(
        mode,
        channels={"kind": "index"}
        if channel == "index"
        else {"kind": "components", "names": [channel]},
    )
    fields.pop("kind")
    if mode == "indexed":
        fields["palette_frame_number"] = 1
    if name == "color-curve":
        fields["points"] = [{"input": 100, "output": value}]
    else:
        color = {
            "kind": "rgba",
            "red": value,
            "green": value,
            "blue": value,
            "alpha": value,
        }
        if mode == "indexed":
            color = {"kind": "palette-index", "index": value}
        elif mode == "grayscale":
            color = {"kind": "grayscale", "gray": value, "alpha": value}
        fields.update({"from": color, "to": color, "tolerance": 255})
    fields.update(options)
    return run(
        "filter",
        name,
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        **fields,
    )


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
def test_alpha_deletion_counts_one_linked_image_and_reports_all_consumers(
    tmp_path, runtime, name
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "target_scene.lua", source=source, mode="linked")
    original = source.read_bytes()
    code, result = apply_filter(name, source, target, channel="alpha")
    assert code == 0, result
    assert result["processed_image_numbers"] == [1]
    assert len(result["affected_cels"]) == 2
    assert all(effect["after"] is None for effect in result["cel_effects"])
    assert result["images"][0]["after_content_digest"] is None
    assert observe_images(runtime, target)["cels"] == []
    if name == "replace-color":
        assert result["changed_pixel_count"] == 1
    assert source.read_bytes() == original


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
def test_selection_coordinates_and_partial_alpha_trim(tmp_path, runtime, name):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "target_scene.lua", source=source, mode="selection")
    code, result = apply_filter(
        name,
        source,
        target,
        channel="alpha",
        selection={
            "kind": "all",
            "rectangle": {"x": 1, "y": 0, "width": 1, "height": 1},
        },
    )
    assert code == 0, result
    cel = observe_images(runtime, target)["cels"][0]
    assert (cel["x"], cel["width"], cel["pixels"]) == (2, 1, [200 | (255 << 24)])
    assert result["cel_effects"][0]["after"]["x"] == 2
    if name == "replace-color":
        assert result["changed_pixel_count"] == 1


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
def test_empty_selection_preserves_pixels_and_reports_noop(tmp_path, runtime, name):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="rgb")
    before = observe_images(runtime, source)
    code, result = apply_filter(name, source, target, selection={"kind": "empty"})
    assert code == 0, result
    assert result["changed"] is False
    assert observe_images(runtime, target) == before
    if name == "replace-color":
        assert result["changed_pixel_count"] == 0


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
@pytest.mark.parametrize("target_kind", ["tilemap", "mixed", "all"])
def test_any_resolved_tilemap_rejects_whole_operation(
    tmp_path, runtime, name, target_kind
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="rgb")
    original = source.read_bytes()
    cels = (
        {"kind": "all"}
        if target_kind == "all"
        else {
            "kind": "selected",
            "layers": [
                {"layer_path": [n]}
                for n in ([2] if target_kind == "tilemap" else [1, 2])
            ],
            "frame_numbers": [1],
        }
    )
    code, result = apply_filter(name, source, target, cels_target=cels)
    assert code != 0
    assert result["code"] == "filter_unsupported_document"
    assert not target.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
def test_ordinary_pixels_preserve_unrelated_tilemap(tmp_path, runtime, name):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="rgb")
    before = observe_images(runtime, source)
    code, result = apply_filter(name, source, target)
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after["tiles"] == before["tiles"]
    assert after["cels"][1] == before["cels"][1]


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
def test_background_alpha_refuses_and_background_color_is_supported(
    tmp_path, runtime, name
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime, "hue_source.lua", source=source, mode="rgb", background="true"
    )
    original = source.read_bytes()
    code, result = apply_filter(name, source, target, channel="alpha")
    assert code != 0
    assert result["code"] == "filter_unsupported_document"
    assert not target.exists()
    assert source.read_bytes() == original
    code, result = apply_filter(name, source, target, channel="red", value=42)
    assert code == 0, result
    assert all(
        pixel & 255 == 42
        for pixel in observe_images(runtime, target)["cels"][0]["pixels"]
    )


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
def test_cartesian_targets_include_empty_slots_without_inventing_cels(
    tmp_path, runtime, name
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "target_scene.lua", source=source, mode="cartesian")
    code, result = apply_filter(
        name,
        source,
        target,
        cels_target={
            "kind": "selected",
            "layers": [{"layer_path": [1]}, {"layer_path": [2]}],
            "frame_numbers": [1, 2, 3],
        },
    )
    assert code == 0, result
    assert len(result["requested_intersections"]) == 6
    assert len(result["existing_target_cels"]) == 3
    assert result["processed_image_numbers"] == [1, 2, 3]
    assert len(observe_images(runtime, target)["cels"]) == 3


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
def test_indexed_component_lookup_uses_explicit_palette_basis(tmp_path, runtime, name):
    from tests.filter.test_e2e_filter_targets import (
        _palette_observation,
        _palette_source,
    )

    source = tmp_path / "source.aseprite"
    _palette_source(runtime, source, "indexed")
    observed = {}
    for basis in (1, 2):
        target = tmp_path / f"basis-{basis}.aseprite"
        options = {"palette_frame_number": basis}
        if name == "color-curve":
            options["points"] = [
                {"input": 0, "output": 0},
                {"input": 170, "output": 255},
            ]
        else:
            options.update(
                {
                    "from": {"kind": "palette-index", "index": 2},
                    "to": {"kind": "palette-index", "index": 2},
                    "tolerance": 60,
                }
            )
        code, result = apply_filter(name, source, target, mode="indexed", **options)
        assert code == 0, result
        assert result["palette_basis"]["frame_number"] == basis
        assert {cel["frame_number"] for cel in result["existing_target_cels"]} == {1}
        observed[basis] = _palette_observation(runtime, target)
        assert observed[basis]["anchor_pixel"] == 1
    # Indexed Color Curve consumes the palette through native projection;
    # Replace Color resolves both input colors in the requested palette.
    assert observed[1]["target_pixel"] == 2
    assert observed[2]["target_pixel"] == 1


def test_replace_index_must_exist_in_requested_palette(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="indexed")
    before = source.read_bytes()
    code, result = apply_filter(
        "replace-color", source, target, mode="indexed", channel="index", value=4
    )
    assert code != 0
    assert result["code"] == "filter_invalid_target"
    assert not target.exists()
    assert source.read_bytes() == before
