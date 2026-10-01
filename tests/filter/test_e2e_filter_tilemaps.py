"""Native Manual Tilemap Filter execution through the installed CLI."""

import pytest

from tests.filter.support import apply, native_script, observe_images, pixels

pytestmark = pytest.mark.e2e

PARTIAL_MASK = {
    "kind": "mask",
    "bounds": {"x": 0, "y": 0, "width": 2, "height": 2},
    "rows": [
        {"y": 0, "runs": [{"x": 0, "length": 1}]},
        {"y": 1, "runs": [{"x": 0, "length": 2}]},
    ],
}


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


@pytest.mark.parametrize(
    "linked,red,processed", [(True, 120, [1]), (False, 180, [1, 2])]
)
def test_shared_tile_reports_all_cels_and_native_cel_image_dedup(
    tmp_path, runtime, linked, red, processed
):
    source, target = tmp_path / "shared.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime, "tilemap_sharing.lua", source=source, linked=str(linked).lower()
    )
    before = observe_images(runtime, source)
    code, result = apply(
        source,
        target,
        pixels(
            tileset_mode="manual",
            channels={"kind": "components", "names": ["red"]},
            cels_target={
                "kind": "selected",
                "layers": [{"layer_path": [1]}],
                "frame_numbers": [1, 2],
            },
            selection={
                "kind": "all",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
            },
        ),
    )
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after["cels"] == before["cels"]
    assert after["tiles"][0] == before["tiles"][0]
    assert after["tiles"][2] == before["tiles"][2]
    assert after["tiles"][1]["pixels"] == [100 << 24 | 20 << 16 | 40 << 8 | red]
    assert (
        result["requested_tileset_mode"] == result["observed_tileset_mode"] == "manual"
    )
    assert result["processed_image_numbers"] == processed
    assert all(
        image["image_kind"] == "tilemap-placement" and not image["changed"]
        for image in result["images"]
    )
    assert len(result["changed_tiles"]) == 1
    changed = result["changed_tiles"][0]
    assert (changed["tileset_index"], changed["tile_index"], changed["tile_key"]) == (
        1,
        1,
        "existing-key",
    )
    refs = {
        (tuple(c["layer_path"]), c["frame_number"]): c
        for c in changed["referencing_cels"]
    }
    assert set(refs) == {((1,), 1), ((1,), 2), ((1,), 3), ((2,), 3), ((3,), 3)}
    for frame in (1, 2):
        assert "direct-target" in refs[((1,), frame)]["relationships"]
    assert "shared-cel-image" in refs[((1,), 2)]["relationships"]
    assert "shared-cel-image" in refs[((1,), 3)]["relationships"]
    assert "direct-target" not in refs[((1,), 3)]["relationships"]
    for layer in (2, 3):
        assert refs[((layer,), 3)]["relationships"] == ["shared-tile"]
        assert refs[((layer,), 3)]["image_number"] is None


@pytest.mark.parametrize("flags", [n << 29 for n in range(8)])
@pytest.mark.parametrize("offset", [-1, 1])
def test_partial_selection_flags_offsets_and_clipping_match_native(
    tmp_path, runtime, flags, offset
):
    source, target, reference = (
        tmp_path / name
        for name in ("source.aseprite", "target.aseprite", "native.aseprite")
    )
    native_script(
        runtime, "tilemap_spatial.lua", source=source, flags=flags, offset=offset
    )
    native_script(runtime, "tilemap_spatial.lua", source=source, target=reference)
    before = observe_images(runtime, source)
    code, result = apply(
        source,
        target,
        pixels(
            tileset_mode="manual",
            selection=PARTIAL_MASK,
            channels={"kind": "components", "names": ["red"]},
        ),
    )
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after == observe_images(runtime, reference)
    assert after["cels"] == before["cels"]
    assert after["tiles"][0] == before["tiles"][0]
    assert after["tiles"][2] == before["tiles"][2]


def test_rectangular_diagonal_tile_matches_native(tmp_path, runtime):
    source, target, reference = (
        tmp_path / name
        for name in ("source.aseprite", "target.aseprite", "native.aseprite")
    )
    native_script(
        runtime,
        "tilemap_spatial.lua",
        source=source,
        flags=0x20000000,
        offset=-1,
        width=3,
    )
    native_script(runtime, "tilemap_spatial.lua", source=source, target=reference)
    code, result = apply(
        source,
        target,
        pixels(
            tileset_mode="manual",
            selection=PARTIAL_MASK,
            channels={"kind": "components", "names": ["red"]},
        ),
    )
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, reference)


def test_empty_selection_preserves_shared_tiles(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap_sharing.lua", source=source, linked="false")
    before = observe_images(runtime, source)
    code, result = apply(
        source,
        target,
        pixels(
            tileset_mode="manual",
            cels_target={"kind": "all"},
            selection={"kind": "empty"},
        ),
    )
    assert code == 0, result
    assert result["selection"] == {"kind": "empty"}
    assert result["changed"] is False and result["changed_tiles"] == []
    assert observe_images(runtime, target) == before


def test_mixed_image_and_tilemap_targets_publish_together(tmp_path, runtime):
    source, target = tmp_path / "mixed.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="rgb")
    original = source.read_bytes()
    target.write_bytes(b"replace old target")
    code, result = apply(
        source,
        target,
        pixels(
            tileset_mode="manual",
            cels_target={"kind": "all"},
            channels={"kind": "components", "names": ["red"]},
        ),
        overwrite=True,
    )
    assert code == 0, result
    assert [(item["image_kind"], item["changed"]) for item in result["images"]] == [
        ("ordinary", True),
        ("tilemap-placement", False),
    ]
    after = observe_images(runtime, target)
    assert after["cels"][0]["pixels"][0] & 0xFF == 120
    assert after["tiles"][1]["pixels"][0] & 0xFF == 120
    assert result["changed_tiles"][0]["referencing_cels"][0]["layer_path"] == [2]
    assert source.read_bytes() == original


def test_all_excludes_noneditable_targets_but_reports_shared_tile_effects(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap_sharing.lua", source=source, linked="false")
    code, result = apply(
        source, target, pixels(tileset_mode="manual", cels_target={"kind": "all"})
    )
    assert code == 0, result
    assert len(result["existing_target_cels"]) == 3
    assert len(result["excluded_layers"]) == 2
    assert len(result["changed_tiles"][0]["referencing_cels"]) == 5
    original = source.read_bytes()
    prior = target.read_bytes()
    selected = {
        "kind": "selected",
        "layers": [{"layer_path": [1]}, {"layer_path": [2]}],
        "frame_numbers": [1, 3],
    }
    code, result = apply(
        source,
        target,
        pixels(tileset_mode="manual", cels_target=selected),
        overwrite=True,
    )
    assert code == 2 and result["code"] == "filter_invalid_target", result
    assert source.read_bytes() == original and target.read_bytes() == prior
