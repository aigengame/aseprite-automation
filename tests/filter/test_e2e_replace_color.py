"""Replace Color uses native matching and observes actual stored-pixel changes."""

import pytest

from tests.filter.support import FIXTURES, observe_images, pixels
from tests.native_invocation import expect_success, run_lua
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


def test_equal_colors_with_positive_tolerance_still_normalize_neighbors(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    lua = run_lua(FIXTURES / "source.lua", runtime, source=source, mode="rgb")
    assert lua.returncode == 0, process_diagnostics(lua)
    original = source.read_bytes()
    options = pixels(channels={"kind": "components", "names": ["red"]})
    options.pop("kind")
    color = {"kind": "rgba", "red": 100, "green": 0, "blue": 0, "alpha": 255}
    result = expect_success(
        "filter replace-color",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "tolerance": 60,
            "from": color,
            "to": color,
            **options,
        },
    )
    assert result["changed_pixel_count"] == 1
    assert "matched_pixel_count" not in result
    assert result["changed"] is True
    assert observe_images(runtime, target)["cels"][0]["pixels"] == [
        100 | (60 << 8) | (20 << 16) | (255 << 24),
        200 | (100 << 8) | (40 << 16) | (128 << 24),
        100 | (20 << 8) | (10 << 16) | (255 << 24),
    ]
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "mode,channel",
    [
        ("rgb", "red"),
        ("rgb", "green"),
        ("rgb", "blue"),
        ("rgb", "alpha"),
        ("grayscale", "gray"),
        ("grayscale", "alpha"),
        ("indexed", "index"),
        ("indexed", "red"),
        ("indexed", "alpha"),
    ],
)
@pytest.mark.parametrize("tolerance", [0, 60])
def test_replace_matches_native_in_each_mode(
    tmp_path, runtime, mode, channel, tolerance
):
    import json

    source, target, native = (
        tmp_path / name
        for name in ("source.aseprite", "target.aseprite", "native.aseprite")
    )
    lua = run_lua(FIXTURES / "source.lua", runtime, source=source, mode=mode)
    assert lua.returncode == 0, process_diagnostics(lua)
    options = pixels(
        mode,
        channels={"kind": "index"}
        if channel == "index"
        else {"kind": "components", "names": [channel]},
    )
    options.pop("kind")
    if mode == "indexed":
        options["palette_frame_number"] = 1
        colors = {
            "from": {"kind": "palette-index", "index": 1},
            "to": {"kind": "palette-index", "index": 2},
        }
    elif mode == "grayscale":
        colors = {
            "from": {"kind": "grayscale", "gray": 100, "alpha": 255},
            "to": {"kind": "grayscale", "gray": 180, "alpha": 128},
        }
    else:
        colors = {
            "from": {"kind": "rgba", "red": 100, "green": 60, "blue": 20, "alpha": 255},
            "to": {"kind": "rgba", "red": 150, "green": 90, "blue": 30, "alpha": 128},
        }
    before = observe_images(runtime, source)
    lua = run_lua(
        FIXTURES / "replace_native.lua",
        runtime,
        source=source,
        target=native,
        channels=json.dumps([channel]),
        tolerance=tolerance,
        **{name: json.dumps(value) for name, value in colors.items()},
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "filter replace-color",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "tolerance": tolerance,
            **colors,
            **options,
        },
    )
    after = observe_images(runtime, target)
    assert after == observe_images(runtime, native)
    assert result["changed_pixel_count"] == sum(
        a != b for a, b in zip(before["cels"][0]["pixels"], after["cels"][0]["pixels"])
    )


@pytest.mark.parametrize("linked", [False, True])
def test_transparent_replacement_counts_native_expansion_once(
    tmp_path, runtime, linked
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    lua = run_lua(
        FIXTURES / "replace_expansion.lua",
        runtime,
        source=source,
        linked=linked,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    before = source.read_bytes()
    options = pixels(
        channels={"kind": "components", "names": ["red", "green", "blue", "alpha"]}
    )
    options.pop("kind")
    result = expect_success(
        "filter replace-color",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "tolerance": 0,
            "from": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 0},
            "to": {"kind": "rgba", "red": 255, "green": 0, "blue": 0, "alpha": 255},
            **options,
        },
    )
    assert result["changed_pixel_count"] == 3
    assert result["processed_image_numbers"] == [1]
    expected = [0xFF0000FF, 0xFFFF0000, 0xFF0000FF, 0xFF0000FF]
    cels = observe_images(runtime, target)["cels"]
    assert len(cels) == (2 if linked else 1)
    assert all(
        cel["pixels"] == expected and cel["x"] == 0 and cel["width"] == 4
        for cel in cels
    )
    assert all(
        effect["before"]["width"] == 1 and effect["after"]["width"] == 4
        for effect in result["cel_effects"]
    )
    assert source.read_bytes() == before
