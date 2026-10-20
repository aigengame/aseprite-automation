"""Tile color applications agree with the independent native Manual oracle."""

import json

import pytest

from tests.filter.support import FIXTURES, apply, pixels, rgb_palette_colors
from tests.native_invocation import run_lua
from tests.support import inject_palette_change, process_diagnostics

pytestmark = pytest.mark.e2e


def create(runtime, source, mode):
    lua = run_lua(
        FIXTURES / "tilemap_applications.lua",
        runtime,
        action="create",
        source=source,
        mode=mode,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    inject_palette_change(
        source,
        [
            (0, 0, 0, 0),
            (80, 40, 20, 100),
            (120, 40, 20, 101),
            (160, 40, 20, 200),
            (160, 40, 20, 200),
        ],
        frame_number=2,
    )


def observe(runtime, source, mode):
    response = source.with_suffix(".json")
    lua = run_lua(
        FIXTURES / "tilemap_applications.lua",
        runtime,
        action="observe",
        source=source,
        mode=mode,
        response=response,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    return json.loads(response.read_text())


def test_gray_tile_channels_and_alpha_match_native(tmp_path, runtime):
    source, target, oracle = [
        tmp_path / f"{name}.aseprite" for name in ("source", "target", "oracle")
    ]
    create(runtime, source, "grayscale")
    original = source.read_bytes()
    before = observe(runtime, source, "grayscale")
    lua = run_lua(
        FIXTURES / "tilemap_applications.lua",
        runtime,
        action="native",
        source=source,
        target=oracle,
        mode="grayscale",
        brightness=50,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    code, result = apply(
        source,
        target,
        pixels(
            "grayscale",
            tileset_mode="manual",
            channels={"kind": "components", "names": ["gray"]},
        ),
    )
    assert code == 0, result
    after = observe(runtime, target, "grayscale")
    assert after == observe(runtime, oracle, "grayscale")
    assert after["resolved"] == [[120, 100], [150, 101], [180, 102]]
    assert after["palettes"] == before["palettes"]
    assert after["maps"] == before["maps"]
    assert after["tiles"][0] == before["tiles"][0]
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original


@pytest.mark.parametrize("kind", ["rgb", "indexed", "rgb-palette-colors"])
@pytest.mark.parametrize(
    "channels", [["red"], ["green"], ["blue"], ["red", "green", "blue"]]
)
def test_tile_application_palette_basis_and_native_alpha(
    tmp_path, runtime, kind, channels
):
    mode = "rgb" if kind == "rgb-palette-colors" else kind
    source, target, oracle = [
        tmp_path / f"{name}.aseprite" for name in ("source", "target", "oracle")
    ]
    create(runtime, source, mode)
    original = source.read_bytes()
    before = observe(runtime, source, mode)
    options = {
        "tileset_mode": "manual",
        "channels": {"kind": "components", "names": channels},
    }
    if kind == "rgb-palette-colors":
        application = rgb_palette_colors(palette_frame_number=2, **options)
    elif kind == "indexed":
        application = pixels(mode, palette_frame_number=2, **options)
    else:
        application = pixels(mode, **options)
    lua = run_lua(
        FIXTURES / "tilemap_applications.lua",
        runtime,
        action="native",
        source=source,
        target=oracle,
        mode=mode,
        brightness=50,
        palette=kind == "rgb-palette-colors",
        channels=",".join(channels),
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    code, result = apply(source, target, application)
    assert code == 0, result
    after = observe(runtime, target, mode)
    assert after == observe(runtime, oracle, mode)
    assert after["maps"] == before["maps"]
    assert after["tiles"][0] == before["tiles"][0]
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original
    assert [change["frame"] for change in before["palettes"]] == [1, 2]
    if kind == "indexed":
        assert result["palette_basis"]["palette_frame_number"] == 2
        assert after["palettes"] == before["palettes"]
        assert (
            after["tiles"][1][1] == 0
        )  # Transparent stored Index remains transparent.
        assert before["resolved"][0][-1] == 100
        if channels == ["red"]:
            assert after["tiles"][1][0] == 2
            assert (
                after["resolved"][0][-1] == 101
            )  # Quantization changes resolved Alpha.
    elif kind == "rgb-palette-colors":
        assert result["palette_basis"]["palette_frame_number"] == 2
        assert after["palettes"][0] == before["palettes"][0]
        assert after["resolved"][2] == [80, 40, 20, 101]
        assert [c[-1] for c in after["resolved"]] == [100, 100, 101]
        if channels == ["red"]:
            assert after["palettes"][1]["entries"][1] == [120, 40, 20, 100]
            assert after["resolved"][:2] == [[120, 40, 20, 100], [120, 40, 20, 100]]
    else:
        assert after["palettes"] == before["palettes"]
        assert [c[-1] for c in after["resolved"]] == [100, 100, 101]
        if channels == ["red"]:
            assert after["resolved"] == [
                [120, 40, 20, 100],
                [120, 40, 20, 100],
                [120, 40, 20, 101],
            ]


@pytest.mark.parametrize("kind", ["rgb", "grayscale", "indexed", "rgb-palette-colors"])
def test_zero_tile_application_preserves_palette_and_duplicate_indexes(
    tmp_path, runtime, kind
):
    mode = "rgb" if kind == "rgb-palette-colors" else kind
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    create(runtime, source, mode)
    original = source.read_bytes()
    before = observe(runtime, source, mode)
    options = {"tileset_mode": "manual"}
    if kind == "rgb-palette-colors":
        application = rgb_palette_colors(palette_frame_number=2, **options)
    elif kind == "indexed":
        application = pixels(mode, palette_frame_number=2, **options)
    else:
        application = pixels(mode, **options)
    code, result = apply(source, target, application, brightness=0, contrast=0)
    assert code == 0, result
    assert observe(runtime, target, mode) == before
    assert result["changed"] is False
    assert result["processed_image_numbers"] == []
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original
