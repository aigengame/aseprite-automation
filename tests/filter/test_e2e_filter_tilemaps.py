"""Native Manual Tilemap Filter execution through the installed CLI."""

import pytest

from tests.filter.support import apply, native_script, observe_images, pixels

pytestmark = pytest.mark.e2e


def test_manual_rgb_tile_filter_preserves_map_empty_and_unused_tiles(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="rgb", only="true")
    original = source.read_bytes()
    before = observe_images(runtime, source)
    code, result = apply(
        source,
        target,
        pixels(
            tileset_mode="manual",
            cels_target={"kind": "all"},
            channels={"kind": "components", "names": ["red"]},
        ),
    )
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after["tiles"][1]["pixels"] == [100 << 24 | 20 << 16 | 40 << 8 | 120]
    assert after["tiles"][0] == before["tiles"][0]
    assert after["tiles"][2] == before["tiles"][2]
    assert after["tiles"][1]["data"] == before["tiles"][1]["data"]
    assert after["cels"] == before["cels"]
    assert after["palette"] == before["palette"]
    assert result["changed"] is True
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original
