"""Color Curve is executed by Aseprite and verified after reopening the Target."""

import pytest

from tests.filter.support import native_script, observe_images, pixels, run

pytestmark = pytest.mark.e2e


def test_constant_red_curve_preserves_other_components_and_source(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="rgb")
    original = source.read_bytes()
    options = pixels(channels={"kind": "components", "names": ["red"]})
    options.pop("kind")
    code, result = run(
        "filter",
        "color-curve",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        points=[{"input": 100, "output": 42}],
        **options,
    )
    assert code == 0, result
    assert result["changed"] is True
    assert result["persisted_reopen_verified"] is True
    after = observe_images(runtime, target)
    assert after["cels"][0]["pixels"] == [
        42 | (60 << 8) | (20 << 16) | (255 << 24),
        42 | (100 << 8) | (40 << 16) | (128 << 24),
        42 | (20 << 8) | (10 << 16) | (255 << 24),
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
@pytest.mark.parametrize(
    "coordinates",
    [[(0, 0), (255, 255)], [(0, 255), (255, 0)], [(50, 230), (128, 20), (200, 180)]],
)
def test_curves_match_direct_native_command(
    tmp_path, runtime, mode, channel, coordinates
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
    points = [{"input": x, "output": y} for x, y in coordinates]
    native_script(
        runtime,
        "curve_native.lua",
        source=source,
        target=native,
        points=json.dumps(points),
        channels=json.dumps([channel]),
    )
    code, result = run(
        "filter",
        "color-curve",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        points=points,
        **options,
    )
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, native)
    assert result["points"] == points
    assert result["palette_before"] == result["palette_after"]
