"""Native Despeckle through the public Filter surface."""

import pytest

from tests.filter.support import native_script, observe_images, pixels, run

pytestmark = pytest.mark.e2e


def pixel_input(mode="rgb", **options):
    selected = pixels(mode, **options)
    del selected["kind"]
    return selected


def apply(source, target, selected, width=3, height=1, tiled_mode="none", **intent):
    return run(
        "filter",
        "despeckle",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=intent.pop("in_place", False),
        overwrite=intent.pop("overwrite", False),
        pixels=selected,
        width=width,
        height=height,
        tiled_mode=tiled_mode,
        **intent,
    )


def test_despeckle_uses_native_median_and_verifies_persistence(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="grayscale")
    original = source.read_bytes()
    code, result = apply(source, target, pixel_input("grayscale"))
    assert code == 0, result
    assert result["anchor"] == {"x": 1, "y": 0}
    assert result["sample_count"] == 3
    assert result["persisted_reopen_verified"] is True
    assert result["processed_image_numbers"] == [1]
    assert result["changed"] is True
    observed = observe_images(runtime, target)
    assert [value & 255 for value in observed["cels"][0]["pixels"]] == [100, 100, 40]
    assert source.read_bytes() == original


def channel_sets(names):
    from itertools import combinations

    return [
        list(combo)
        for size in range(1, len(names) + 1)
        for combo in combinations(names, size)
    ]


RGB_SETS = channel_sets(["red", "green", "blue", "alpha"])
GRAY_SETS = channel_sets(["gray", "alpha"])
INDEXED_SETS = [names for names in RGB_SETS if "green" in names]
FLAGS = {"red": 1, "green": 2, "blue": 4, "alpha": 8, "gray": 16}


@pytest.mark.parametrize(
    "mode,names",
    [("rgb", n) for n in RGB_SETS]
    + [("grayscale", n) for n in GRAY_SETS]
    + [("indexed", n) for n in INDEXED_SETS]
    + [("indexed", [])],
)
def test_every_channel_branch_matches_independent_native_command(
    tmp_path, runtime, mode, names
):
    source, target, baseline = [
        tmp_path / name
        for name in ("source.aseprite", "target.aseprite", "native.aseprite")
    ]
    native_script(runtime, "despeckle_source.lua", source=source, mode=mode)
    flags = sum(FLAGS[name] for name in names) if names else 32
    native_script(
        runtime,
        "despeckle_native_baseline.lua",
        source=source,
        target=baseline,
        channels=flags,
        width=3,
        height=1,
        tiled_mode="none",
    )
    channels = {"kind": "components", "names": names} if names else {"kind": "index"}
    selected = pixel_input(mode, channels=channels)
    if mode == "indexed":
        selected["palette_frame_number"] = 1
    code, result = apply(source, target, selected)
    assert code == 0, result
    before, after = observe_images(runtime, source), observe_images(runtime, target)
    assert after == observe_images(runtime, baseline)
    assert after["palette"] == before["palette"]
    assert result["channels"] == channels
    assert result["persisted_reopen_verified"] is True
    if names:
        pixel = after["cels"][0]["pixels"][1]
        components = (
            after["palette"][pixel]
            if mode == "indexed"
            else [
                (pixel >> (8 * index)) & 255
                for index in range(2 if mode == "grayscale" else 4)
            ]
        )
        labels = (
            ["gray", "alpha"]
            if mode == "grayscale"
            else ["red", "green", "blue", "alpha"]
        )
        original = [200, 60] if mode == "grayscale" else [200, 40, 100, 60]
        median = [100, 128] if mode == "grayscale" else [100, 100, 100, 128]
        assert components == [
            median[i] if name in names else original[i] for i, name in enumerate(labels)
        ]


@pytest.mark.parametrize(
    "width,height", [(2, 2), (3, 3), (100, 1), (1, 100), (100, 100)]
)
@pytest.mark.parametrize("tiled_mode", ["none", "x", "y", "both"])
def test_windows_and_edges_match_native(tmp_path, runtime, width, height, tiled_mode):
    source, target, baseline = [
        tmp_path / name
        for name in ("source.aseprite", "target.aseprite", "native.aseprite")
    ]
    native_script(
        runtime, "despeckle_source.lua", source=source, mode="grayscale", grid="true"
    )
    native_script(
        runtime,
        "despeckle_native_baseline.lua",
        source=source,
        target=baseline,
        channels=16,
        width=width,
        height=height,
        tiled_mode=tiled_mode,
    )
    code, result = apply(
        source, target, pixel_input("grayscale"), width, height, tiled_mode
    )
    assert code == 0, result
    assert result["anchor"] == {"x": width // 2, "y": height // 2}
    assert result["sample_count"] == width * height
    after = observe_images(runtime, target)
    assert after == observe_images(runtime, baseline)
    # Independent acceptance oracle: upper median, repeat/wrap at each Image edge.
    original = [p & 255 for p in observe_images(runtime, source)["cels"][0]["pixels"]]

    def coordinate(value, tiled):
        return value % 3 if tiled else min(2, max(0, value))

    expected = []
    for y in range(3):
        for x in range(3):
            samples = [
                original[
                    coordinate(y + dy - height // 2, tiled_mode in ("y", "both")) * 3
                    + coordinate(x + dx - width // 2, tiled_mode in ("x", "both"))
                ]
                for dy in range(height)
                for dx in range(width)
            ]
            expected.append(sorted(samples)[len(samples) // 2])
    actual = [p & 255 for p in after["cels"][0]["pixels"]]
    if width == 100 and height == 1 and tiled_mode in ("none", "y"):
        # Native 1.3.18.5 advances getx while its address waits at the left edge.
        # The owner accepted native output; do not implement ideal clamping in SPA.
        assert actual == [100] * 3 + [200] * 3 + [40] * 3
        assert actual != expected
    else:
        assert actual == expected


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_one_by_one_reports_native_unchanged_pixels(tmp_path, runtime, mode):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "despeckle_source.lua", source=source, mode=mode)
    selected = pixel_input(mode)
    if mode == "indexed":
        selected.update(channels={"kind": "index"}, palette_frame_number=1)
    code, result = apply(source, target, selected, 1, 1)
    assert code == 0, result
    assert result["changed"] is False
    assert result["processed_image_numbers"] == [1]
    assert observe_images(runtime, target) == observe_images(runtime, source)


@pytest.mark.parametrize(
    "index,components,expected", [(1, False, 1), (1, True, 2), (2, True, 2)]
)
def test_one_by_one_keeps_native_rgb_map_outcome(
    tmp_path, runtime, index, components, expected
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime,
        "despeckle_source.lua",
        source=source,
        mode="indexed",
        duplicate="true",
        index=index,
    )
    channels = (
        {"kind": "components", "names": ["red", "green", "blue", "alpha"]}
        if components
        else {"kind": "index"}
    )
    code, result = apply(
        source,
        target,
        pixel_input("indexed", palette_frame_number=1, channels=channels),
        1,
        1,
    )
    assert code == 0, result
    assert result["changed"] == (index != expected)
    assert result["processed_image_numbers"] == [1]
    assert observe_images(runtime, target)["cels"][0]["pixels"] == [expected]
    assert result["palette_before"] == result["palette_after"]


@pytest.mark.parametrize("names", [n for n in RGB_SETS if "green" not in n])
def test_defective_indexed_channels_refuse_without_publishing(tmp_path, runtime, names):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "despeckle_source.lua", source=source, mode="indexed")
    original = source.read_bytes()
    target.write_bytes(b"keep existing target")
    code, result = apply(
        source,
        target,
        pixel_input(
            "indexed",
            palette_frame_number=1,
            channels={"kind": "components", "names": names},
        ),
        overwrite=True,
    )
    assert code != 0 and result["code"] == "filter_unsupported_document", result
    assert "Green" in result["message"]
    assert (
        source.read_bytes() == original
        and target.read_bytes() == b"keep existing target"
    )


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_background_alpha_refuses_whole_request(tmp_path, runtime, mode):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime, "despeckle_source.lua", source=source, mode=mode, background="true"
    )
    selected = pixel_input(
        mode,
        channels={
            "kind": "components",
            "names": ["gray", "alpha"] if mode == "grayscale" else ["green", "alpha"],
        },
    )
    if mode == "indexed":
        selected["palette_frame_number"] = 1
    original = source.read_bytes()
    code, result = apply(source, target, selected)
    assert code != 0 and result["code"] == "filter_unsupported_document", result
    assert "Background" in result["message"]
    assert not target.exists() and source.read_bytes() == original


@pytest.mark.parametrize("target_kind", ["tilemap", "mixed", "all", "ordinary"])
def test_tilemap_boundary(tmp_path, runtime, target_kind):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="rgb")
    original = source.read_bytes()
    selected = pixel_input()
    if target_kind == "all":
        selected["cels_target"] = {"kind": "all"}
    else:
        selected["cels_target"]["layers"] = [
            {"layer_path": [number]}
            for number in (
                {"tilemap": [2], "mixed": [1, 2], "ordinary": [1]}[target_kind]
            )
        ]
    code, result = apply(source, target, selected)
    if target_kind != "ordinary":
        assert code != 0 and result["code"] == "filter_unsupported_document", result
        assert "Tilemap" in result["message"]
        assert not target.exists()
    else:
        assert code == 0, result
        before, after = observe_images(runtime, source), observe_images(runtime, target)
        assert before["tiles"] == after["tiles"]
        assert before["cels"][1:] == after["cels"][1:]
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "selection",
    [
        {"kind": "empty"},
        {"kind": "all", "rectangle": {"x": 1, "y": 0, "width": 1, "height": 1}},
    ],
)
def test_explicit_selection_and_linked_target(tmp_path, runtime, selection):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime, "despeckle_source.lua", source=source, mode="grayscale", linked="true"
    )
    before = observe_images(runtime, source)
    code, result = apply(source, target, pixel_input("grayscale", selection=selection))
    assert code == 0, result
    assert result["processed_image_numbers"] == [1]
    assert {cel["frame_number"] for cel in result["affected_cels"]} == {1, 2}
    assert len(result["existing_target_cels"]) == 1
    after = observe_images(runtime, target)
    expected = [100, 100, 40] if selection["kind"] != "empty" else [100, 200, 40]
    assert len(after["cels"]) == 2
    for cel in after["cels"]:
        assert [p & 255 for p in cel["pixels"]] == expected
    assert after["palette"] == before["palette"]
