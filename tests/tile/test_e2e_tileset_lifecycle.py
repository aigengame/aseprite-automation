"""Tileset lifecycle through the public CLI and persisted native documents."""

from pathlib import Path

import pytest

from tests.native_invocation import expect_success, run
from tests.support import tileset_lifecycle_sprite
from tests.tile.support import lifecycle_sprite, verify_tileset_lifecycle

pytestmark = pytest.mark.e2e


def files(source: Path, target: Path) -> dict:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": source == target,
        "overwrite": source == target,
    }


def test_remove_orphan_keeps_referenced_tileset(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "removed.aseprite"
    lifecycle_sprite(runtime, source)
    original = source.read_bytes()
    result = expect_success(
        "tileset remove",
        {**files(source, target), "target": {"tileset_name": "orphan"}},
    )
    assert result["removed_tileset"]["name"] == "orphan"
    assert result["removed_tileset"]["layers"] == []
    assert [item["name"] for item in result["tilesets"]] == ["terrain"]
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original
    observed = expect_success("tileset list", {"sprite_file": str(target)})
    assert len(observed["tilesets"]) == 1


def test_remove_referenced_reports_every_layer_and_keeps_target(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    lifecycle_sprite(runtime, source)
    target.write_bytes(b"previous target")
    original = source.read_bytes()
    outcome = run(
        "tileset remove",
        {
            **files(source, target),
            "overwrite": True,
            "target": {"tileset_name": "terrain"},
        },
    )
    result = outcome.envelope
    assert outcome.returncode != 0, result
    assert result["code"] == "tileset_in_use"
    assert {item["name"] for item in result["details"]["layers"]} == {"map", "peer"}
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"


def rebind(source: Path, target: Path, **extra: object) -> dict:
    return {
        **files(source, target),
        "layer": {"layer_name": "map"},
        "target": {"tileset_name": "destination"},
        "mapping": {"kind": "by_key"},
        "grid_policy": "require_equal",
        **extra,
    }


@pytest.mark.parametrize("explicit", [False, True])
def test_rebind_preserves_flags_links_metadata_and_other_layer(
    tmp_path: Path, runtime, explicit: bool
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "rebound.aseprite"
    tileset_lifecycle_sprite(runtime, source, unkeyed=3)
    original = source.read_bytes()
    mapping = (
        {"kind": "by_key"}
        if not explicit
        else {
            "kind": "explicit",
            "entries": [
                {"source_key": "a", "target": {"kind": "tile", "tile_key": "a"}},
                {"source_key": "b", "target": {"kind": "empty"}},
            ],
        }
    )
    result = expect_success(
        "layer set-tileset", rebind(source, target, mapping=mapping)
    )
    assert result["tileset"]["name"] == "destination"
    assert len(result["cels"]) == 2
    assert [item["target_index"] for item in result["tile_mapping"]] == [
        2,
        0 if explicit else 1,
    ]
    verify_tileset_lifecycle(runtime, target, explicit=str(explicit).lower())
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "parameters,code",
    [
        ({"unkeyed": 1}, "tile_key_missing"),
        ({"duplicate": "true"}, "tile_key_ambiguous"),
        ({"target_duplicate": "true"}, "tile_key_ambiguous"),
        ({"target_missing": "true"}, "tile_key_missing"),
        ({"flagged_empty": "true"}, "tile_key_missing"),
        ({"invalid_key": "true"}, "tile_key_missing"),
    ],
)
def test_rebind_refuses_unresolved_used_keys(
    tmp_path: Path, runtime, parameters: dict, code: str
) -> None:
    source = tmp_path / "source.aseprite"
    tileset_lifecycle_sprite(runtime, source, **parameters)
    original = source.read_bytes()
    outcome = run("layer set-tileset", rebind(source, source))
    result = outcome.envelope
    assert outcome.returncode != 0, result
    assert result["code"] == code
    assert source.read_bytes() == original


def test_rebind_grid_policy_keeps_cells_and_positions(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "rebound.aseprite"
    tileset_lifecycle_sprite(runtime, source, width=5, height=4)
    outcome = run("layer set-tileset", rebind(source, target))
    refused = outcome.envelope
    assert (
        outcome.returncode != 0 and refused["details"]["reason"] == "grid_mismatch"
    ), refused
    assert not target.exists()
    result = expect_success(
        "layer set-tileset", rebind(source, target, grid_policy="use_target")
    )
    for cel in result["cels"]:
        assert cel["position"] == {"x": -3, "y": 7}
        assert cel["cell_size"] == {"width": 3, "height": 1}
        assert cel["before_coverage"] == {"x": -3, "y": 7, "width": 6, "height": 3}
        assert cel["canvas_coverage"] == {"x": -3, "y": 7, "width": 15, "height": 4}
    verify_tileset_lifecycle(runtime, target)


@pytest.mark.parametrize("transparent,high_index", [(0, 7), (7, 2)])
def test_rebind_rejects_invalid_index_or_transparency_in_linked_usage_frame(
    tmp_path: Path, runtime, transparent: int, high_index: int
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    tileset_lifecycle_sprite(
        runtime, source, mode="indexed", transparent=transparent, high_index=high_index
    )
    inject_palette_change(source, [(i, 20, 30, 255) for i in range(4)], frame_number=2)
    target.write_bytes(b"previous target")
    original = source.read_bytes()
    outcome = run("layer set-tileset", rebind(source, target, overwrite=True))
    result = outcome.envelope
    assert outcome.returncode != 0, result
    assert result["code"] == "tileset_lifecycle_invalid"
    assert result["details"]["reason"] == "palette_index"
    assert result["details"]["frame_number"] == 2
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"


def test_indexed_rebind_checks_only_tiles_used_in_each_frame(
    tmp_path: Path, runtime
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    tileset_lifecycle_sprite(runtime, source, mode="indexed", separate_frames="true")
    inject_palette_change(
        source, [(i, 20, 30, 0 if i == 0 else 255) for i in range(4)], frame_number=1
    )
    inject_palette_change(
        source, [(i, 40, 50, 0 if i == 0 else 255) for i in range(8)], frame_number=2
    )
    result = expect_success("layer set-tileset", rebind(source, target))
    assert [
        (check["frame_number"], check["tile_indexes"])
        for check in result["palette_checks"]
    ] == [(1, [2]), (2, [1])]
    assert [
        check["effective_palette"]["palette_size"] for check in result["palette_checks"]
    ] == [4, 8]


@pytest.mark.parametrize("as_plan", [False, True])
@pytest.mark.parametrize("transparent,high_index,invalid_index", [(0, 7, 7), (6, 2, 6)])
def test_indexed_refusal_reports_inherited_palette_basis_without_publication(
    tmp_path: Path,
    runtime,
    as_plan: bool,
    transparent: int,
    high_index: int,
    invalid_index: int,
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    tileset_lifecycle_sprite(
        runtime,
        source,
        mode="indexed",
        inherited_palette="true",
        transparent=transparent,
        high_index=high_index,
    )
    inject_palette_change(
        source, [(i, 20, 30, 0 if i == 0 else 255) for i in range(4)], frame_number=2
    )
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    intent = {
        "layer": {"layer_name": "map"},
        "target": {"tileset_name": "destination"},
        "mapping": {"kind": "by_key"},
        "grid_policy": "require_equal",
    }
    publication = {**files(source, target), "overwrite": True}
    if as_plan:
        outcome = run(
            "plan run",
            {
                "plan": {
                    **publication,
                    "steps": [{"operation": "layer set-tileset", "input": intent}],
                }
            },
        )
        result = outcome.envelope
    else:
        outcome = run("layer set-tileset", {**publication, **intent})
        result = outcome.envelope
    assert outcome.returncode != 0 and result["code"] == "tileset_lifecycle_invalid", (
        result
    )
    details = result["details"]
    assert details["reason"] == "palette_index"
    assert details["frame_number"] == 3
    assert details["palette_frame_number"] == 2
    assert details["palette_size"] == 4
    assert details["invalid_index"] == invalid_index
    assert details["tile_index"] == (1 if transparent == 0 else None)
    assert details["step_number"] == (1 if as_plan else None)
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"
    assert not list(tmp_path.glob(".*.staged.aseprite"))


def test_indexed_linked_rebind_allows_different_valid_frame_palettes(
    tmp_path: Path, runtime
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    tileset_lifecycle_sprite(runtime, source, mode="indexed")
    inject_palette_change(
        source, [(i, 40, 50, 0 if i == 0 else 255) for i in range(8)], frame_number=2
    )
    result = expect_success("layer set-tileset", rebind(source, target))
    assert [check["frame_number"] for check in result["palette_checks"]] == [1, 2]
    assert [check["tile_indexes"] for check in result["palette_checks"]] == [
        [1, 2],
        [1, 2],
    ]
    verify_tileset_lifecycle(runtime, target)


@pytest.mark.parametrize("keys", [["a"], ["a", "b", "unused"]])
def test_explicit_mapping_requires_exactly_used_keys(
    tmp_path: Path, runtime, keys: list[str]
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    tileset_lifecycle_sprite(runtime, source)
    original = source.read_bytes()
    mapping = {
        "kind": "explicit",
        "entries": [{"source_key": key, "target": {"kind": "empty"}} for key in keys],
    }
    outcome = run("layer set-tileset", rebind(source, target, mapping=mapping))
    result = outcome.envelope
    assert outcome.returncode != 0, result
    assert result["code"] == "tileset_lifecycle_invalid"
    assert result["details"]["reason"] in {"mapping_incomplete", "mapping_invalid"}
    assert source.read_bytes() == original
    assert not target.exists()


@pytest.mark.parametrize("as_plan", [False, True])
@pytest.mark.parametrize("replace_a", ["identity", "empty", "b"])
def test_same_tileset_checks_only_changed_usage(
    tmp_path: Path, runtime, as_plan: bool, replace_a: str
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    tileset_lifecycle_sprite(runtime, source, mode="indexed")
    # Native round-trippable Palette sizes: existing b is invalid only at Frame 2.
    for frame, size in [(1, 4), (2, 2)]:
        inject_palette_change(
            source,
            [(i, 20, 30, 0 if i == 0 else 255) for i in range(size)],
            frame_number=frame,
        )
    original = source.read_bytes()
    mapping = (
        {"kind": "by_key"}
        if replace_a == "identity"
        else {
            "kind": "explicit",
            "entries": [
                {
                    "source_key": "a",
                    "target": {"kind": "empty"}
                    if replace_a == "empty"
                    else {"kind": "tile", "tile_key": "b"},
                },
                {"source_key": "b", "target": {"kind": "tile", "tile_key": "b"}},
            ],
        }
    )
    intent = {
        "layer": {"layer_name": "map"},
        "target": {"tileset_name": "source"},
        "mapping": mapping,
        "grid_policy": "require_equal",
    }
    if as_plan:
        outcome = run(
            "plan run",
            {
                "plan": {
                    **files(source, target),
                    "steps": [{"operation": "layer set-tileset", "input": intent}],
                }
            },
        )
        result = outcome.envelope
    else:
        outcome = run("layer set-tileset", {**files(source, target), **intent})
        result = outcome.envelope
    assert source.read_bytes() == original
    if replace_a == "b":
        # A new b usage must be checked even though b already occurred here.
        assert (
            outcome.returncode != 0 and result["code"] == "tileset_lifecycle_invalid"
        ), result
        assert result["details"]["reason"] == "palette_index"
        assert result["details"]["frame_number"] == 2
        assert not target.exists()
        return
    assert outcome.returncode == 0, result
    evidence = result["steps"][0]["result"] if as_plan else result
    assert evidence["palette_checks"] == []
    assert [cel["changed_cells"] for cel in evidence["cels"]] == [
        0 if replace_a == "identity" else 1
    ] * 2
    observed = expect_success(
        "tilemap get",
        {
            "sprite_file": str(target),
            "target": {"layer": {"layer_name": "map"}, "frame_number": 2},
            "rectangle": {"x": 0, "y": 0, "width": 3, "height": 1},
        },
    )
    assert [
        item["placement"]["tile_key"] for item in observed["snapshot"]["entries"]
    ] == (["a", "b"] if replace_a == "identity" else ["b"])
