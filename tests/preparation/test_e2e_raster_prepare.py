"""Prepare selected raster bytes through the installed CLI and native owners."""

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from tests.native_invocation import expect_success, run
from tests.preparation.support import specification
from tests.support import icc_fixture_path, process_diagnostics

pytestmark = pytest.mark.e2e


def prepare_request(source, target, spec, *, intent=None):
    """Return a `raster prepare` request that must not replace target.

    The intent is `initial` when the caller gives none.
    """
    return {
        "raster_file": str(source),
        "intent": intent or {"kind": "initial"},
        "specification": spec,
        "destination": {"path": str(target), "if_exists": "fail"},
    }


def save_rgba(path, size, pixels, **options):
    image = Image.new("RGBA", size)
    image.putdata(pixels)
    image.save(path, **options)
    return path.read_bytes()


def origin_spec(width, height, mode="rgba"):
    spec = specification(mode)
    spec["crop"]["rectangle"].update(width=width, height=height)
    spec["resize"].update(width=width, height=height)
    spec["canvas"] = {"width": width, "height": height}
    spec["anchors"] = [{"name": "origin", "x": 0, "y": 0}]
    spec["alignment"] = {"primary_anchor": "origin", "position": {"x": 0, "y": 0}}
    return spec


def rgba_pixels(target, mode):
    with Image.open(target) as image:
        assert image.mode == ("P" if mode == "indexed" else "RGBA")
        assert image.info["srgb"] == 0
        assert "icc_profile" not in image.info
        return list(image.convert("RGBA").get_flattened_data())


def test_prepare_rgba_thresholds_aligns_and_publishes(tmp_path):
    source, target = tmp_path / "input.png", tmp_path / "prepared.png"
    pixels = [
        (180, 70, 30, 255),
        (30, 90, 180, 255),
        (44, 11, 66, 0),
        (180, 70, 30, 127),
        (30, 90, 180, 128),
        (0, 0, 0, 0),
    ]
    image = Image.new("RGBA", (3, 2))
    image.putdata(pixels)
    image.save(source)
    original = source.read_bytes()
    request = {
        "raster_file": str(source),
        "intent": {"kind": "initial"},
        "specification": specification(),
        "destination": {"path": str(target), "if_exists": "fail"},
    }
    result = expect_success("raster prepare", request)
    facts = result["reproduction"]
    assert facts["source_identity"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert facts["geometry"]["offset"] == {"x": 1, "y": 1}
    assert facts["geometry"]["anchors"] == [{"name": "foot", "x": 2, "y": 3}]
    expected = [(0, 0, 0, 0)] * 20
    expected[6], expected[7], expected[12] = pixels[0], pixels[1], (30, 90, 180, 255)
    with Image.open(target) as prepared:
        assert prepared.mode == "RGBA"
        assert prepared.info["srgb"] == 0
        assert "icc_profile" not in prepared.info
        assert list(prepared.get_flattened_data()) == expected
    assert source.read_bytes() == original
    assert (
        result["artifact"]["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    )
    assert not list(tmp_path.glob(".*.staged*"))


def test_prepare_rgb_input_nearest_resizes_complete_pixels(tmp_path):
    source, target = tmp_path / "rgb.png", tmp_path / "rgba.png"
    image = Image.new("RGB", (2, 1))
    image.putdata([(180, 70, 30), (30, 90, 180)])
    image.save(source)
    original = source.read_bytes()
    spec = origin_spec(2, 1)
    spec["resize"].update(width=4, height=2)
    spec["canvas"] = {"width": 4, "height": 2}
    spec["mapping"].update(
        rgb_map_algorithm="default", color_best_fit_criteria="default"
    )
    result = expect_success("raster prepare", prepare_request(source, target, spec))
    assert result["reproduction"]["mapping"]["requested_rgb_map_algorithm"] == "default"
    assert result["reproduction"]["mapping"]["effective_rgb_map_algorithm"] == "octree"
    assert (
        rgba_pixels(target, "rgba")
        == [
            (180, 70, 30, 255),
            (180, 70, 30, 255),
            (30, 90, 180, 255),
            (30, 90, 180, 255),
        ]
        * 2
    )
    assert source.read_bytes() == original


@pytest.mark.parametrize("transparent_index", [0, 7, 255])
@pytest.mark.parametrize("all_opaque", [False, True])
def test_prepare_preserves_complete_palette_and_both_formats_match(
    tmp_path, transparent_index, all_opaque
):
    source = tmp_path / "input.png"
    red, blue, clear = (180, 70, 30, 255), (30, 90, 180, 255), (0, 0, 0, 0)
    pixels = [red, blue, red if all_opaque else (44, 11, 66, 0)]
    original = save_rgba(source, (3, 1), pixels)
    count = 256 if transparent_index == 255 else 8
    entries = [(255, 255, 255, 255)] * count
    visible = [index for index in range(count) if index != transparent_index]
    entries[visible[0]], entries[visible[1]], entries[visible[2]] = red, blue, red
    entries[transparent_index] = clear
    expected = [red, blue, red if all_opaque else clear]
    decoded = []
    for mode in ("indexed", "rgba"):
        spec = origin_spec(3, 1, mode)
        spec["palette"] = {
            "entries": [
                dict(zip(("red", "green", "blue", "alpha"), c)) for c in entries
            ],
            "transparent_index": transparent_index,
        }
        target = tmp_path / f"{mode}.png"
        result = expect_success("raster prepare", prepare_request(source, target, spec))
        assert result["reproduction"]["content"]["palette"] == spec["palette"]
        decoded.append(rgba_pixels(target, mode))
        if mode == "indexed":
            with Image.open(target) as image:
                # PLTE length/order, including unused and duplicate entries, is exact.
                assert image.getpalette() == [
                    channel for c in entries for channel in c[:3]
                ]
                assert image.info["transparency"] == transparent_index
                indices = list(image.get_flattened_data())
                assert [entries[index] for index in indices] == expected
                assert all(index < count for index in indices)
                if not all_opaque:
                    assert indices[-1] == transparent_index
    assert decoded == [expected, expected]
    assert source.read_bytes() == original


@pytest.mark.parametrize("threshold", [1, 128, 255])
def test_prepare_threshold_edges_and_empty_explicit_crop(tmp_path, threshold):
    source = tmp_path / "input.png"
    pixels = [(180, 70, 30, alpha) for alpha in (0, threshold - 1, threshold, 255)]
    save_rgba(source, (4, 1), pixels)
    spec = origin_spec(4, 1)
    spec["alpha_threshold"] = threshold
    target = tmp_path / "threshold.png"
    result = expect_success("raster prepare", prepare_request(source, target, spec))
    assert rgba_pixels(target, "rgba") == [(0, 0, 0, 0)] * 2 + [(180, 70, 30, 255)] * 2
    spec["crop"]["rectangle"]["width"] = 2
    spec["resize"]["width"] = 2
    spec["canvas"]["width"] = 2
    empty = tmp_path / "empty.png"
    result = expect_success("raster prepare", prepare_request(source, empty, spec))
    assert rgba_pixels(empty, "rgba") == [(0, 0, 0, 0)] * 2
    assert result["reproduction"]["content"]["alpha_max"] == 0


@pytest.mark.parametrize(
    ("rounding", "height", "offset", "other"),
    [
        ("toward-zero", 1, (1, 1), (7, 5)),
        ("floor", 1, (2, 1), (8, 5)),
        ("ceil", 2, (1, 2), (7, 10)),
        ("nearest-away-from-zero", 2, (2, 2), (8, 10)),
    ],
)
def test_automatic_crop_fractional_scale_and_outside_anchors(
    tmp_path, rounding, height, offset, other
):
    source = tmp_path / "input.png"
    pixels = [(44, 11, 66, 0)] * 12
    pixels[5], pixels[6] = (180, 70, 30, 128), (30, 90, 180, 255)
    original = save_rgba(source, (4, 3), pixels)
    spec = specification()
    spec.update(
        crop={"kind": "automatic"},
        resize={"kind": "scale", "factor": 1.5},
        rounding=rounding,
        canvas={"width": 8, "height": 8},
        anchors=[{"name": "foot", "x": 0, "y": 0}, {"name": "outside", "x": 5, "y": 5}],
        alignment={"primary_anchor": "foot", "position": {"x": 0, "y": 0}},
    )
    target = tmp_path / "prepared.png"
    result = expect_success("raster prepare", prepare_request(source, target, spec))
    geometry = result["reproduction"]["geometry"]
    assert geometry["crop"] == {"x": 1, "y": 1, "width": 2, "height": 1}
    assert geometry["resized"] == {"width": 3, "height": height}
    assert geometry["offset"] == dict(zip(("x", "y"), offset))
    assert geometry["anchors"] == [
        {"name": "foot", "x": 0, "y": 0},
        {"name": "outside", "x": other[0], "y": other[1]},
    ]
    output = rgba_pixels(target, "rgba")
    for y in range(8):
        for x in range(8):
            covered = (
                offset[0] <= x < offset[0] + 3 and offset[1] <= y < offset[1] + height
            )
            assert (output[y * 8 + x][3] == 255) == covered
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "source_kind", ["none", "srgb", "display_p3_cc0", "display_p3"]
)
def test_prepare_normalizes_color_before_threshold_and_mapping(
    tmp_path, runtime, source_kind
):
    source = tmp_path / "input.png"
    options = {}
    if source_kind == "srgb":
        metadata = PngImagePlugin.PngInfo()
        metadata.add(b"sRGB", bytes([3]))
        options["pnginfo"] = metadata
    elif source_kind in ("display_p3_cc0", "display_p3"):
        options["icc_profile"] = icc_fixture_path(source_kind).read_bytes()
    original = save_rgba(
        source,
        (3, 1),
        [(180, 70, 30, 128), (180, 70, 30, 127), (44, 11, 66, 0)],
        **options,
    )
    converted = (
        (195, 60, 2, 255)
        if source_kind in ("display_p3_cc0", "display_p3")
        else (180, 70, 30, 255)
    )
    outputs = []
    for mode in ("rgba", "indexed"):
        spec = origin_spec(3, 1, mode)
        spec["palette"]["entries"].append(
            {"red": 195, "green": 60, "blue": 2, "alpha": 255}
        )
        target = tmp_path / f"{mode}.png"
        outcome = run("raster prepare", prepare_request(source, target, spec))
        result = outcome.envelope
        if (
            source_kind in ("display_p3_cc0", "display_p3")
            and "aseprite_convert_color_profile" not in runtime.verified_capabilities
        ):
            assert (
                outcome.returncode != 0 and result["code"] == "runtime_incompatible"
            ), result
            assert not target.exists()
            continue
        assert outcome.returncode == 0, process_diagnostics(outcome.process)
        assert result["reproduction"]["profile"] == {
            "source_kind": "icc"
            if source_kind in ("display_p3_cc0", "display_p3")
            else source_kind,
            "source_icc_identity": source_kind
            if source_kind in ("display_p3_cc0", "display_p3")
            else None,
            "assumption": "srgb" if source_kind == "none" else None,
            "effective": "srgb",
            "converted": source_kind in ("display_p3_cc0", "display_p3"),
        }
        outputs.append(rgba_pixels(target, mode))
    if outputs:
        assert outputs == [[converted, (0, 0, 0, 0), (0, 0, 0, 0)]] * 2
    assert source.read_bytes() == original


def test_prepare_wizard_frozen_source_and_reproduce(tmp_path):
    example = Path(__file__).resolve().parents[2] / "examples/wizard_cast_v2/inputs"
    source = example / "raw/idle-concept.png"
    original = source.read_bytes()
    recipe = json.loads((example / "preparation.json").read_text())
    colors = [
        tuple(bytes.fromhex(color.removeprefix("#"))) + (255,)
        for color in recipe["palette"].values()
    ]
    colors.append((0, 0, 0, 0))
    spec = origin_spec(1060, 1484, "indexed")
    spec.update(
        resize={"kind": "scale", "factor": 0.125},
        canvas={"width": 224, "height": 224},
        anchors=[
            {"name": "foot", "x": 535, "y": 1426},
            {"name": "gem", "x": 843, "y": 211},
        ],
        alignment={"primary_anchor": "foot", "position": {"x": 84, "y": 212}},
        palette={
            "entries": [
                dict(zip(("red", "green", "blue", "alpha"), color)) for color in colors
            ],
            "transparent_index": 24,
        },
    )
    first, second = tmp_path / "wizard.png", tmp_path / "reproduced.png"
    result = expect_success("raster prepare", prepare_request(source, first, spec))
    retained = result["reproduction"]
    assert retained["geometry"]["resized"] == {"width": 133, "height": 186}
    assert retained["geometry"]["offset"] == {"x": 17, "y": 33}
    assert retained["geometry"]["anchors"] == [
        {"name": "foot", "x": 84, "y": 212},
        {"name": "gem", "x": 123, "y": 59},
    ]
    reproduced = expect_success(
        "raster prepare",
        prepare_request(
            source, second, spec, intent={"kind": "reproduce", "expected": retained}
        ),
    )
    assert reproduced["reproduction"] == retained
    assert rgba_pixels(first, "indexed") == rgba_pixels(second, "indexed")
    assert set(rgba_pixels(first, "indexed")) <= set(colors)
    assert source.read_bytes() == original
