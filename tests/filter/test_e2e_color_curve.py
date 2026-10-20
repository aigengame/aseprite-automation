"""Color Curve is executed by Aseprite and verified after reopening the Target."""

import pytest

from tests.filter.support import FIXTURES, observe_images, pixels
from tests.native_invocation import expect_success, run_lua
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


def test_constant_red_curve_preserves_other_components_and_source(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    lua = run_lua(FIXTURES / "source.lua", runtime, source=source, mode="rgb")
    assert lua.returncode == 0, process_diagnostics(lua)
    original = source.read_bytes()
    options = pixels(channels={"kind": "components", "names": ["red"]})
    options.pop("kind")
    result = expect_success(
        "filter color-curve",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "points": [{"input": 100, "output": 42}],
            **options,
        },
    )
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
    points = [{"input": x, "output": y} for x, y in coordinates]
    lua = run_lua(
        FIXTURES / "curve_native.lua",
        runtime,
        source=source,
        target=native,
        points=json.dumps(points),
        channels=json.dumps([channel]),
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "filter color-curve",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "points": points,
            **options,
        },
    )
    assert observe_images(runtime, target) == observe_images(runtime, native)
    assert result["points"] == points
    assert result["palette_before"] == result["palette_after"]
