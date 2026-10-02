"""Replace Color uses native matching and observes actual stored-pixel changes."""

import pytest

from tests.filter.support import native_script, observe_images, pixels, run

pytestmark = pytest.mark.e2e


def test_equal_colors_with_positive_tolerance_still_normalize_neighbors(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="rgb")
    original = source.read_bytes()
    options = pixels(channels={"kind": "components", "names": ["red"]})
    options.pop("kind")
    color = {"kind": "rgba", "red": 100, "green": 0, "blue": 0, "alpha": 255}
    code, result = run(
        "filter",
        "replace-color",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        tolerance=60,
        **{"from": color, "to": color},
        **options,
    )
    assert code == 0, result
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
    native_script(runtime, "source.lua", source=source, mode=mode)
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
    native_script(
        runtime,
        "replace_native.lua",
        source=source,
        target=native,
        channels=json.dumps([channel]),
        tolerance=tolerance,
        **{name: json.dumps(value) for name, value in colors.items()},
    )
    code, result = run(
        "filter",
        "replace-color",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        tolerance=tolerance,
        **colors,
        **options,
    )
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after == observe_images(runtime, native)
    assert result["changed_pixel_count"] == sum(
        a != b for a, b in zip(before["cels"][0]["pixels"], after["cels"][0]["pixels"])
    )
