"""Verified Tileset atlas and map pairs through the installed public CLI."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.aseprite.aseprite import probe
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


def request(source: Path, root: Path, **overrides: object) -> dict:
    return {
        "source_sprite_file": str(source),
        "tileset": {"tileset_name": "source"},
        "target": {"layer": {"layer_name": "map"}, "frame_number": 1},
        "rectangle": {"x": 0, "y": 0, "width": 3, "height": 1},
        "columns": 3,
        "image": {"path": str(root / "atlas.png"), "if_exists": "fail"},
        "metadata": {"path": str(root / "map.json"), "if_exists": "fail"},
        **overrides,
    }


def test_export_full_keyed_tileset_and_one_map_region(tmp_path: Path, runtime) -> None:
    source = tmp_path / "source.aseprite"
    fixture(source, runtime, script="tileset_lifecycle.lua")
    before = source.read_bytes()
    code, result = run("export", "tileset", **request(source, tmp_path))
    assert code == 0, result
    assert source.read_bytes() == before
    assert [item["role"] for item in result["artifacts"]] == [
        "tileset-image",
        "map-data",
    ]
    metadata = json.loads((tmp_path / "map.json").read_text())
    assert metadata == result["map"]
    assert metadata["tileset"]["base_index"] == 11
    assert metadata["tilemap"]["position"] == {"x": -3, "y": 7}
    assert [item.get("tile_key") for item in metadata["atlas"]["tiles"]] == [
        None,
        "a",
        "b",
        "unused",
    ]
    snapshot = metadata["snapshot"]
    assert snapshot["complete"] is True
    assert snapshot["default"] == {"kind": "empty"}
    assert [entry["tile_x"] for entry in snapshot["entries"]] == [0, 1]
    assert snapshot["entries"][0]["placement"] == {
        "kind": "tile",
        "tile_index": 1,
        "tile_key": "a",
        "flip_x": True,
        "flip_y": True,
        "flip_diagonal": True,
    }
    with Image.open(tmp_path / "atlas.png") as image:
        assert image.size == (6, 6)
        rgba = image.convert("RGBA")
        assert [
            rgba.getpixel(point) for point in [(0, 0), (2, 0), (4, 0), (0, 3), (2, 3)]
        ] == [
            (0, 0, 0, 0),
            (21, 30, 40, 255),
            (22, 30, 40, 255),
            (23, 30, 40, 255),
            (0, 0, 0, 0),
        ]


PALETTE = [
    (11, 22, 33, 255),
    (255, 255, 0, 255),
    (80, 90, 100, 128),
    (80, 90, 100, 128),
    (50, 60, 70, 1),
    (90, 10, 40, 0),
    (255, 255, 255, 255),
    (4, 5, 6, 255),
]


def matrix_source(
    tmp_path: Path, runtime, mode="rgb", profile="none", **params
) -> Path:
    from importlib.resources import files

    from spa.authoring.color.profile import PROFILE_ICC_RESOURCES
    from tests.support import inject_palette_change

    source = tmp_path / "source.aseprite"
    if profile in ("linear_srgb", "display_p3"):
        resource = next(
            item
            for item in PROFILE_ICC_RESOURCES
            if item.parameter_name == "profile_" + profile
        )
        params["icc_file"] = str(files("spa.kernel").joinpath(resource.package_path))
    fixture(
        source,
        runtime,
        script=str(Path(__file__).parent / "fixtures" / "tileset_export.lua"),
        mode=mode,
        profile=profile,
        **params,
    )
    if mode == "indexed" and "palette_size" not in params:
        inject_palette_change(source, PALETTE, frame_number=2)
    return source


def matrix_request(source: Path, tmp_path: Path) -> dict:
    return request(
        source,
        tmp_path,
        tileset={"tileset_name": "terrain"},
        target={"layer": {"layer_name": "map"}, "frame_number": 2},
        rectangle={"x": 0, "y": 0, "width": 3, "height": 2},
        columns=2,
    )


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("profile", ["none", "srgb", "linear_srgb", "display_p3"])
def test_preserve_mode_palette_profile_and_exact_tile_channels(
    tmp_path: Path, runtime, mode: str, profile: str
) -> None:
    from importlib.resources import files

    from spa.adapters.png_input import decode_png_artifact
    from spa.authoring.color.profile import PROFILE_ICC_RESOURCES

    source = matrix_source(tmp_path, runtime, mode, profile)
    before = source.read_bytes()
    code, result = run("export", "tileset", **matrix_request(source, tmp_path))
    assert source.read_bytes() == before
    if mode == "grayscale" and profile in ("linear_srgb", "display_p3"):
        assert code != 0 and result["code"] == "tileset_export_unsupported", result
        assert result["details"]["reason"] == "color_profile"
        assert not (tmp_path / "atlas.png").exists()
        assert not (tmp_path / "map.json").exists()
        return
    assert code == 0, json.dumps(result, indent=2)
    decoded = decode_png_artifact((tmp_path / "atlas.png").read_bytes())
    assert (decoded.width, decoded.height, decoded.color_mode) == (4, 4, mode)
    assert decoded.color_profile == (
        "icc" if profile in ("linear_srgb", "display_p3") else profile
    )
    if decoded.icc_bytes is not None:
        resource = next(
            item
            for item in PROFILE_ICC_RESOURCES
            if item.parameter_name == "profile_" + profile
        )
        assert (
            decoded.icc_bytes
            == files("spa.kernel").joinpath(resource.package_path).read_bytes()
        )
    if profile == "srgb":
        assert decoded.srgb_rendering_intent == 0
    with Image.open(tmp_path / "atlas.png") as image:
        if mode == "indexed":
            assert image.mode == "P"
            assert [
                image.getpixel(p)
                for p in [(2, 0), (3, 0), (2, 1), (3, 1), (0, 2), (2, 2)]
            ] == [0, 1, 2, 7, 4, 7]
            assert decoded.entries == tuple(PALETTE[:7] + [(4, 5, 6, 0)])
            assert image.convert("RGBA").getpixel((3, 0)) == (255, 255, 0, 255)
            assert result["map"]["atlas"]["palette"]["palette_frame_number"] == 2
            assert result["map"]["atlas"]["palette"]["transparent_color_index"] == 7
        elif mode == "rgb":
            rgba = image.convert("RGBA")
            assert [rgba.getpixel(p) for p in [(2, 0), (3, 0), (2, 1), (3, 1)]] == [
                (30, 20, 60, 255),
                (70, 20, 60, 128),
                (110, 20, 60, 1),
                (150, 20, 60, 255),
            ]
        else:
            gray = image.convert("LA")
            assert [gray.getpixel(p) for p in [(2, 0), (3, 0), (2, 1), (3, 1)]] == [
                (30, 255),
                (70, 128),
                (110, 1),
                (150, 255),
            ]
        assert image.convert("RGBA").getpixel((3, 3))[3] == 0
    assert json.loads((tmp_path / "map.json").read_text()) == result["map"]


def test_rgb_tiles_with_more_than_256_colors_do_not_quantize(
    tmp_path: Path, runtime
) -> None:
    source = matrix_source(tmp_path, runtime, large_colors="true")
    code, result = run("export", "tileset", **matrix_request(source, tmp_path))
    assert code == 0, result
    with Image.open(tmp_path / "atlas.png") as image:
        assert image.mode in ("RGB", "RGBA")
        pixels = image.convert("RGBA")
        assert len({pixels.getpixel((257 + x, 0)) for x in range(257)}) == 257
        assert pixels.getpixel((513, 0)) == (0, 1, 20, 255)


@pytest.mark.parametrize(
    "params,reason",
    [
        ({"bad_key": "missing"}, "tile_key_missing"),
        ({"bad_key": "duplicate"}, "tile_key_duplicate"),
        ({"bad_key": "invalid"}, "tile_key_invalid"),
        ({"flagged_zero": "true"}, "placement_invalid"),
        ({"invalid_index": "true"}, "placement_invalid"),
        ({"mode": "indexed", "palette_size": "257"}, "palette_capacity"),
        ({"mode": "indexed", "palette_size": "4"}, "palette_incomplete"),
        (
            {"mode": "indexed", "palette_size": "4", "transparent": "0"},
            "palette_incomplete",
        ),
    ],
)
def test_unkeyed_unused_tiles_bad_placements_and_incomplete_palettes_refuse(
    tmp_path: Path, runtime, params: dict, reason: str
) -> None:
    source = matrix_source(tmp_path, runtime, **params)
    before = source.read_bytes()
    code, result = run("export", "tileset", **matrix_request(source, tmp_path))
    assert code != 0 and result["code"] == "tileset_export_unsupported", result
    assert result["details"]["reason"] == reason
    assert source.read_bytes() == before
    assert (
        not (tmp_path / "atlas.png").exists() and not (tmp_path / "map.json").exists()
    )
    assert not list(tmp_path.glob(".*.staged.*"))


def test_unknown_rgb_icc_refuses_without_implicit_profile_loss(
    tmp_path: Path, runtime
) -> None:
    from PIL import ImageCms

    icc = tmp_path / "other.icc"
    icc.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    source = matrix_source(tmp_path, runtime, profile="custom", icc_file=str(icc))
    before = source.read_bytes()
    code, result = run("export", "tileset", **matrix_request(source, tmp_path))
    assert code != 0 and result["code"] == "tileset_export_unsupported", result
    assert result["details"]["reason"] == "color_profile"
    assert source.read_bytes() == before
    assert (
        not (tmp_path / "atlas.png").exists() and not (tmp_path / "map.json").exists()
    )


def test_subregion_retains_full_atlas_and_reports_selected_coordinates(
    tmp_path: Path, runtime
) -> None:
    source = matrix_source(tmp_path, runtime)
    inputs = matrix_request(source, tmp_path)
    inputs["rectangle"] = {"x": 1, "y": 0, "width": 2, "height": 2}
    code, result = run("export", "tileset", **inputs)
    assert code == 0, result
    assert len(result["map"]["atlas"]["tiles"]) == 3
    assert result["map"]["snapshot"]["rectangle"] == inputs["rectangle"]
    assert [
        (e["tile_x"], e["tile_y"]) for e in result["map"]["snapshot"]["entries"]
    ] == [(2, 0), (1, 1)]


@pytest.mark.parametrize(
    "change,code",
    [
        ({"tileset": {"tileset_name": "unknown"}}, "tileset_missing"),
        (
            {"rectangle": {"x": 3, "y": 0, "width": 1, "height": 1}},
            "tile_region_out_of_bounds",
        ),
        (
            {"target": {"layer": {"layer_name": "map"}, "frame_number": 3}},
            "tilemap_frame_out_of_bounds",
        ),
    ],
)
def test_invalid_target_or_region_refuses_without_output(
    tmp_path: Path, runtime, change: dict, code: str
) -> None:
    source = matrix_source(tmp_path, runtime)
    code_number, result = run(
        "export", "tileset", **(matrix_request(source, tmp_path) | change)
    )
    assert code_number != 0 and result["code"] == code, result
    assert (
        not (tmp_path / "atlas.png").exists() and not (tmp_path / "map.json").exists()
    )


def test_oversized_atlas_reports_allowed_dimensions_without_publication(
    tmp_path: Path, runtime
) -> None:
    source = matrix_source(tmp_path, runtime)
    before = source.read_bytes()
    inputs = matrix_request(source, tmp_path) | {"columns": 2147483647}
    code, result = run("export", "tileset", **inputs)
    assert code == 2 and result["code"] == "tileset_export_unsupported", result
    assert result["details"] == {"kind": "tileset_export", "reason": "atlas_layout"}
    assert "1..2147483647 pixels" in result["message"]
    assert source.read_bytes() == before
    assert not (tmp_path / "atlas.png").exists()
    assert not (tmp_path / "map.json").exists()
    assert not list(tmp_path.glob(".*.staged.*"))
