"""Palette organization through public operations and persisted native documents."""

import json
from pathlib import Path

import pytest

from tests.palette.support import native_script, palette_fixture, run_palette
from tests.support import inject_palette_change

pytestmark = pytest.mark.e2e


def organization_fixture(
    source: Path, runtime, *, mode="cross-range", cross_link=True
) -> None:
    native_script(
        runtime,
        "index_organization.lua",
        source=source,
        mode=mode,
        cross_link=str(cross_link).lower(),
    )
    inject_palette_change(
        source,
        [(10, 20, 30, 255), (40, 80, 220, 255), (20, 200, 40, 128), (50, 60, 70, 0)],
        frame_number=3,
    )


def observe(source: Path, runtime) -> dict:
    response = source.with_suffix(".json")
    native_script(
        runtime, "inspect_index_organization.lua", source=source, response=response
    )
    return json.loads(response.read_text())


def mutation(source: Path, target: Path, **values: object) -> dict:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
        **values,
    }


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_resize_grows_only_the_exact_change_with_explicit_colors(
    tmp_path: Path, runtime, mode: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime, mode)
    original = source.read_bytes()
    code, before = run_palette("palette", "list", sprite_file=str(source))
    assert code == 0, before
    entries = [
        {"index": 4, "color": {"red": 11, "green": 22, "blue": 33, "alpha": 44}},
        {"index": 5, "color": {"red": 55, "green": 66, "blue": 77, "alpha": 88}},
    ]
    code, result = run_palette(
        "palette",
        "resize",
        **mutation(source, target, palette_frame_number=3, size=6, entries=entries),
    )
    assert code == 0, result
    code, after = run_palette("palette", "list", sprite_file=str(target))
    assert code == 0, after
    expected = before["palette_changes"]
    expected[1]["entries"].extend(entries)
    assert after["palette_changes"] == expected
    assert result["palette_changes"] == expected
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original


def test_resize_shrinks_unused_entries_without_changing_pixels(
    tmp_path: Path, runtime
) -> None:
    source, grown, shrunk = (
        tmp_path / name
        for name in ("source.aseprite", "grown.aseprite", "shrunk.aseprite")
    )
    palette_fixture(source, runtime)
    code, original = run_palette("palette", "list", sprite_file=str(source))
    assert code == 0, original
    code, result = run_palette(
        "palette",
        "resize",
        **mutation(
            source,
            grown,
            palette_frame_number=3,
            size=5,
            entries=[
                {"index": 4, "color": {"red": 1, "green": 2, "blue": 3, "alpha": 255}}
            ],
        ),
    )
    assert code == 0, result
    code, result = run_palette(
        "palette",
        "resize",
        **mutation(grown, shrunk, palette_frame_number=3, size=4, entries=[]),
    )
    assert code == 0, result
    assert result["palette_changes"] == original["palette_changes"]


def test_resize_refuses_removing_transparent_index_before_publication(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    code, result = run_palette(
        "palette",
        "resize",
        **mutation(source, target, palette_frame_number=3, size=3, entries=[]),
    )
    assert code != 0 and result["code"] == "palette_transform_rejected", result
    assert result["details"]["reason"] == "transparent_index_removed"
    assert source.read_bytes() == original and target.read_bytes() == b"existing target"


def test_remap_changes_every_unique_indexed_image_and_preserves_tilemap_metadata(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    organization_fixture(source, runtime)
    before = observe(source, runtime)
    original = source.read_bytes()
    mapping = [
        {"old_index": old, "new_index": new} for old, new in enumerate([3, 2, 1, 0])
    ]
    code, result = run_palette(
        "palette", "remap", **mutation(source, target, mapping=mapping)
    )
    assert code == 0, json.dumps(result)
    after = observe(target, runtime)
    assert after["palettes"] == before["palettes"]
    assert result["mapping"] == mapping
    assert after["transparent_color_index"] == 0
    for old, new in zip(before["cels"], after["cels"], strict=True):
        assert new["shared_image_ordinal"] == old["shared_image_ordinal"]
        expected = (
            old["pixels"]
            if old["is_tilemap"]
            else [3 - index for index in old["pixels"]]
        )
        assert new["pixels"] == expected
        for field in (
            "layer_path",
            "frame_number",
            "is_reference",
            "position",
            "opacity",
            "z_index",
        ):
            assert new[field] == old[field]
    for old, new in zip(
        before["tilesets"][0]["tiles"], after["tilesets"][0]["tiles"], strict=True
    ):
        assert new["pixels"] == [3 - index for index in old["pixels"]]
        for field in (
            "tile_index",
            "data",
            "color",
            "properties",
            "spa_properties",
            "other_properties",
        ):
            assert new[field] == old[field]
    assert (
        len(result["affected_images"]) == 9
    )  # one shared ordinary Image, four references, four Tiles
    assert source.read_bytes() == original


@pytest.mark.parametrize("scope", ["sprite", "palette-change"])
def test_reorder_preserves_colors_with_an_explicit_complete_permutation(
    tmp_path: Path, runtime, scope: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    organization_fixture(source, runtime, mode="within-range", cross_link=False)
    before = observe(source, runtime)
    permutation = [3, 2, 1, 0] if scope == "sprite" else [1, 0, 2, 3]
    mapping = [
        {"old_index": old, "new_index": new} for old, new in enumerate(permutation)
    ]
    scope_args = {"scope": scope}
    if scope == "palette-change":
        scope_args["palette_frame_number"] = 1
    code, result = run_palette(
        "palette", "reorder", **mutation(source, target, mapping=mapping, **scope_args)
    )
    assert code == 0, json.dumps(result)
    after = observe(target, runtime)
    assert result["mapping"] == mapping and result["scope"] == scope
    assert after["rendered"] == before["rendered"]
    assert after["transparent_color_index"] == (0 if scope == "sprite" else 3)
    for old, new in zip(before["palettes"], after["palettes"], strict=True):
        if scope == "sprite" or old["frame_number"] == 1:
            for old_index, new_index in enumerate(permutation):
                assert new["entries"][new_index] == old["entries"][old_index]
        else:
            assert new == old
    for old, new in zip(before["cels"], after["cels"], strict=True):
        assert new["shared_image_ordinal"] == old["shared_image_ordinal"]
        changes = not old["is_tilemap"] and (
            scope == "sprite" or old["frame_number"] <= 2
        )
        assert new["pixels"] == (
            [permutation[i] for i in old["pixels"]] if changes else old["pixels"]
        )
    for old, new in zip(
        before["tilesets"][0]["tiles"], after["tilesets"][0]["tiles"], strict=True
    ):
        changes = scope == "sprite" or old["tile_index"] == 1
        assert new["pixels"] == (
            [permutation[i] for i in old["pixels"]] if changes else old["pixels"]
        )
        for field in (
            "tile_index",
            "data",
            "color",
            "properties",
            "spa_properties",
            "other_properties",
        ):
            assert new[field] == old[field]


@pytest.mark.parametrize("conflict", ["linked-cel", "shared-tile"])
def test_palette_change_reorder_refuses_shared_images_outside_the_range(
    tmp_path: Path, runtime, conflict: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    organization_fixture(
        source,
        runtime,
        mode="cross-range" if conflict == "shared-tile" else "within-range",
        cross_link=conflict == "linked-cel",
    )
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    code, result = run_palette(
        "palette",
        "reorder",
        **mutation(
            source,
            target,
            scope="palette-change",
            palette_frame_number=1,
            mapping=[
                {"old_index": i, "new_index": v} for i, v in enumerate([1, 0, 2, 3])
            ],
        ),
    )
    assert code != 0 and result["code"] == "palette_transform_rejected", result
    assert result["details"]["reason"] == "shared_image_outside_range"
    if conflict == "shared-tile":
        tile = result["details"]["tile_uses"][0]
        assert (tile["tileset_index"], tile["tile_index"]) == (1, 1)
        assert {use["palette_frame_number"] for use in tile["cel_uses"]} == {1, 3}
    else:
        assert {use["frame_number"] for use in result["details"]["cel_uses"]} == {
            1,
            2,
            3,
            4,
        }
    assert source.read_bytes() == original and target.read_bytes() == b"existing target"


@pytest.mark.parametrize("mode", ["unused-only", "reference-only"])
def test_shrink_resolves_unused_tiles_and_reference_images(
    tmp_path: Path, runtime, mode: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    organization_fixture(source, runtime, mode=mode)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    code, result = run_palette(
        "palette",
        "resize",
        **mutation(source, target, palette_frame_number=1, size=2, entries=[]),
    )
    assert code != 0 and result["code"] == "palette_transform_rejected", result
    assert (
        result["details"]["reason"] == "index_removed"
        and result["details"]["index"] == 2
    )
    if mode == "unused-only":
        assert result["details"]["tile_uses"] == [
            {"tileset_index": 1, "tile_index": 3, "cel_uses": []}
        ]
    else:
        assert result["details"]["cel_uses"][0]["is_reference"] is True
    assert source.read_bytes() == original and target.read_bytes() == b"existing target"


@pytest.mark.parametrize("mode", ["rgb", "grayscale"])
def test_reorder_nonindexed_palette_leaves_images_and_transparency_unchanged(
    tmp_path: Path, runtime, mode: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime, mode)
    before = observe(source, runtime)
    code, result = run_palette(
        "palette",
        "reorder",
        **mutation(
            source,
            target,
            scope="sprite",
            mapping=[
                {"old_index": i, "new_index": v} for i, v in enumerate([3, 2, 1, 0])
            ],
        ),
    )
    assert code == 0, json.dumps(result)
    after = observe(target, runtime)
    assert after["cels"] == before["cels"]
    assert after["transparent_color_index"] == before["transparent_color_index"]
    assert result["affected_images"] == []


@pytest.mark.parametrize(
    "mapping,expected",
    [
        (
            [{"old_index": 1, "new_index": 2}, {"old_index": 2, "new_index": 1}],
            [2, 3, 1],
        ),
        ([{"old_index": 1, "new_index": 2}], [2, 3, 2]),
    ],
)
def test_sparse_remap_retains_unmapped_indexes_and_persists_tiles(
    tmp_path: Path, runtime, mapping: list, expected: list
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    organization_fixture(source, runtime)
    code, result = run_palette(
        "palette", "remap", **mutation(source, target, mapping=mapping)
    )
    assert code == 0, json.dumps(result)
    after = observe(target, runtime)
    assert after["transparent_color_index"] == 3
    ordinary = next(cel for cel in after["cels"] if cel["layer_path"] == "Ordinary")
    assert ordinary["pixels"] == expected
    assert after["tilesets"][0]["tiles"][1]["pixels"] == [2]


@pytest.mark.parametrize(
    "operation,extra,reason",
    [
        (
            "remap",
            {"mapping": [{"old_index": 1, "new_index": 4}]},
            "invalid_destination",
        ),
        (
            "reorder",
            {
                "scope": "sprite",
                "mapping": [{"old_index": i, "new_index": i} for i in range(3)],
            },
            "permutation_size",
        ),
        (
            "reorder",
            {
                "scope": "palette-change",
                "palette_frame_number": 1,
                "mapping": [{"old_index": i, "new_index": 3 - i} for i in range(4)],
            },
            "transparent_index_moved",
        ),
        (
            "resize",
            {"palette_frame_number": 1, "size": 5, "entries": []},
            "growth_entries",
        ),
    ],
)
def test_organization_refusals_preserve_both_files(
    tmp_path: Path, runtime, operation: str, extra: dict, reason: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    organization_fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    code, result = run_palette(
        "palette", operation, **mutation(source, target, **extra)
    )
    assert code != 0 and result["code"] == "palette_transform_rejected", result
    assert result["details"]["reason"] == reason
    assert source.read_bytes() == original and target.read_bytes() == b"existing target"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "source.aseprite",
        "target.aseprite",
    ]


def test_remap_checks_destinations_against_every_palette_change(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime,
        "index_organization.lua",
        source=source,
        mode="cross-range",
        cross_link="true",
    )
    inject_palette_change(
        source, [(10, 20, 30, 255), (40, 80, 220, 255)], frame_number=3
    )
    code, palette = run_palette(
        "palette", "get", sprite_file=str(source), frame_number=3
    )
    assert code == 0 and len(palette["palette"]["entries"]) == 2
    code, result = run_palette(
        "palette",
        "remap",
        **mutation(source, target, mapping=[{"old_index": 3, "new_index": 2}]),
    )
    assert code != 0 and result["code"] == "palette_transform_rejected", result
    assert (
        result["details"]["palette_frame_number"] == 3
        and result["details"]["index"] == 2
    )
    assert not target.exists()
