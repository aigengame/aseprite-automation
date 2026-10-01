"""Hue/Saturation uses explicit native adjustments through the public CLI."""

import pytest

from tests.filter.support import native_script, observe_images, pixels, run

pytestmark = pytest.mark.e2e


def test_zero_hsl_adjustment_preserves_native_pixels_and_palette(tmp_path, runtime):
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    native_script(runtime, "noop.lua", source=source, mode="rgb")
    original = source.read_bytes()
    before = observe_images(runtime, source)
    code, result = run(
        "filter",
        "hue-saturation",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        application=pixels(),
        adjustment={"mode": "hsl-multiply", "hue": 0, "saturation": 0, "lightness": 0},
    )
    assert code == 0, result
    assert result["operation"] == "spa filter hue-saturation"
    assert result["changed"] is False
    assert result["processed_image_numbers"] == []
    assert result["persisted_reopen_verified"] is True
    assert observe_images(runtime, target) == before
    assert source.read_bytes() == original


def test_alpha_minus_100_reports_native_deletion_including_link_outside_target(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "target_scene.lua", source=source, mode="linked")
    before = source.read_bytes()
    code, result = run(
        "filter",
        "hue-saturation",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        application=pixels(channels={"kind": "components", "names": ["alpha"]}),
        alpha=-100,
    )
    assert code == 0, result
    assert result["changed"] is True
    assert result["images"][0]["after_content_digest"] is None
    assert result["processed_image_numbers"] == [1]
    assert len(result["existing_target_cels"]) == 1
    assert {cel["frame_number"] for cel in result["cel_effects"]} == {1, 2}
    assert all(cel["after"] is None for cel in result["cel_effects"])
    assert observe_images(runtime, target)["cels"] == []
    assert source.read_bytes() == before


# Native command spellings and expected colors are independently observed in
# Aseprite 1.3.18.5, not derived from SPA's mapping or a copied color algorithm.
MODES = [
    ("hsl-multiply", "hsl", [134, 72, 10, 128], 2),
    ("hsv-multiply", "hsv", [120, 60, 0, 128], 3),
    ("hsl-add", "hsl_add", [218, 111, 4, 128], 4),
    ("hsv-add", "hsv_add", [151, 76, 0, 128], 5),
]


def hue(source, target, application, **parameters):
    return run(
        "filter",
        "hue-saturation",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=parameters.pop("in_place", False),
        overwrite=parameters.pop("overwrite", False),
        application=application,
        **parameters,
    )


def application(mode, kind, names):
    channels = {"kind": "components", "names": names}
    if kind == "indexed-palette-entries":
        return {
            "kind": kind,
            "palette_frame_number": 1,
            "entries": {"kind": "selected", "indexes": [1]},
            "channels": channels,
        }
    if kind == "rgb-palette-colors":
        return {
            "kind": kind,
            "palette_frame_number": 1,
            "indexes": [1],
            "channels": channels,
            "cels_target": pixels()["cels_target"],
        }
    result = pixels(mode, channels=channels)
    if mode == "indexed":
        result["palette_frame_number"] = 1
    return result


@pytest.mark.parametrize("public_mode,native_mode,expected,index", MODES)
@pytest.mark.parametrize(
    "color_mode,kind",
    [
        ("rgb", "pixels"),
        ("indexed", "pixels"),
        ("indexed", "indexed-palette-entries"),
        ("rgb", "rgb-palette-colors"),
    ],
)
def test_four_modes_match_direct_native_command_in_each_application(
    tmp_path, runtime, public_mode, native_mode, expected, index, color_mode, kind
):
    source, target, baseline = (
        tmp_path / name
        for name in ("source.aseprite", "target.aseprite", "baseline.aseprite")
    )
    native_script(runtime, "hue_source.lua", source=source, mode=color_mode)
    original = source.read_bytes()
    native_script(
        runtime,
        "hue_native_baseline.lua",
        source=source,
        target=baseline,
        kind=kind,
        native_mode=native_mode,
        channels=7,
        hue=0,
        saturation=30,
        lightness=20,
        alpha=0,
    )
    adjustment = {
        "mode": public_mode,
        "hue": 0,
        "saturation": 30,
        "value" if public_mode.startswith("hsv") else "lightness": 20,
    }
    code, result = hue(
        source,
        target,
        application(color_mode, kind, ["red", "green", "blue"]),
        adjustment=adjustment,
    )
    assert code == 0, result
    assert result["adjustment"] == adjustment
    assert result["changed"] is True
    observed = observe_images(runtime, target)
    assert observed == observe_images(runtime, baseline)
    if kind == "indexed-palette-entries":
        assert observed["cels"][0]["pixels"] == [1] * 3
        assert result["images"] == result["cel_effects"] == []
    else:
        expected_pixel = (
            index
            if color_mode == "indexed"
            else sum(component << (8 * i) for i, component in enumerate(expected))
        )
        assert observed["cels"][0]["pixels"] == [expected_pixel] * 3
    assert observed["palette"][1] == (
        expected if kind != "pixels" else [100, 60, 20, 128]
    )
    assert source.read_bytes() == original


CHANNEL_CASES = [
    (mode, kind, [channel])
    for mode, kind, channels in [
        ("rgb", "pixels", ["red", "green", "blue", "alpha"]),
        ("grayscale", "pixels", ["gray", "alpha"]),
        ("indexed", "pixels", ["red", "green", "blue", "alpha"]),
        ("indexed", "indexed-palette-entries", ["red", "green", "blue", "alpha"]),
        ("rgb", "rgb-palette-colors", ["red", "green", "blue", "alpha"]),
    ]
    for channel in channels
] + [("rgb", "pixels", ["red", "alpha"]), ("grayscale", "pixels", ["gray", "alpha"])]


@pytest.mark.parametrize("mode,kind,names", CHANNEL_CASES)
def test_each_color_and_alpha_channel_matches_direct_native_command(
    tmp_path, runtime, mode, kind, names
):
    source, target, baseline = (
        tmp_path / name
        for name in ("source.aseprite", "target.aseprite", "baseline.aseprite")
    )
    native_script(runtime, "hue_source.lua", source=source, mode=mode)
    parameters = {}
    if any(name != "alpha" for name in names):
        parameters["adjustment"] = (
            {"mode": "grayscale", "lightness": 50}
            if mode == "grayscale"
            else {"mode": "hsl-add", "hue": 30, "saturation": -20, "lightness": 50}
        )
    if "alpha" in names:
        parameters["alpha"] = 50
    flags = sum(
        {"red": 1, "green": 2, "blue": 4, "alpha": 8, "gray": 16}[name]
        for name in names
    )
    native_script(
        runtime,
        "hue_native_baseline.lua",
        source=source,
        target=baseline,
        kind=kind,
        native_mode="hsl_add",
        channels=flags,
        hue=30 if parameters.get("adjustment") and mode != "grayscale" else 0,
        saturation=-20 if parameters.get("adjustment") and mode != "grayscale" else 0,
        lightness=50 if parameters.get("adjustment") else 0,
        alpha=parameters.get("alpha", 0),
    )
    code, result = hue(source, target, application(mode, kind, names), **parameters)
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, baseline)
    assert result["alpha"] == parameters.get("alpha")
    assert result["adjustment"] == parameters.get("adjustment")


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_alpha_adjustment_keeps_transparency_and_reports_native_cel_trim(
    tmp_path, runtime, mode
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime, "hue_source.lua", source=source, mode=mode, transparent="true"
    )
    before = source.read_bytes()
    code, result = hue(source, target, application(mode, "pixels", ["alpha"]), alpha=50)
    assert code == 0, result
    assert result["cel_effects"][0]["before"] == {
        "x": 0,
        "y": 0,
        "width": 3,
        "height": 1,
    }
    assert result["cel_effects"][0]["after"] == {
        "x": 1,
        "y": 0,
        "width": 2,
        "height": 1,
    }
    cel = observe_images(runtime, target)["cels"][0]
    assert (cel["x"], cel["width"]) == (1, 2)
    expected = (
        6
        if mode == "indexed"
        else (
            (192 << 8) | 80
            if mode == "grayscale"
            else (192 << 24) | (20 << 16) | (60 << 8) | 100
        )
    )
    assert cel["pixels"] == [expected, expected]
    assert source.read_bytes() == before


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_alpha_only_zero_is_noop_without_trim_or_requantization(
    tmp_path, runtime, mode
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime, "hue_source.lua", source=source, mode=mode, transparent="true"
    )
    before = observe_images(runtime, source)
    code, result = hue(source, target, application(mode, "pixels", ["alpha"]), alpha=0)
    assert code == 0, result
    assert result["changed"] is False and result["processed_image_numbers"] == []
    assert result["cel_effects"][0]["before"] == result["cel_effects"][0]["after"]
    assert observe_images(runtime, target) == before


@pytest.mark.parametrize("alpha", [0, 50, -100])
def test_background_alpha_rejects_before_publication_including_zero(
    tmp_path, runtime, alpha
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime, "hue_source.lua", source=source, mode="rgb", background="true"
    )
    before = source.read_bytes()
    target.write_bytes(b"existing target")
    code, result = hue(
        source,
        target,
        application("rgb", "pixels", ["alpha"]),
        alpha=alpha,
        overwrite=True,
    )
    assert code != 0 and result["code"] == "filter_unsupported_document", result
    assert "Background" in result["message"]
    assert source.read_bytes() == before
    assert target.read_bytes() == b"existing target"
