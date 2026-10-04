"""Tilemap region writes through the public CLI and persisted native Images."""

import json
from pathlib import Path

import pytest

from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


def placement(key: str = "c", **flags: bool) -> dict:
    return {
        "kind": "tile",
        "tile_key": key,
        "flip_x": False,
        "flip_y": False,
        "flip_diagonal": False,
        **flags,
    }


def files(source: Path, destination: Path, frame: int = 1, **extra: object) -> dict:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(destination),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_name": "map"}, "frame_number": frame},
        **extra,
    }


def test_set_replaces_sparse_region_and_preserves_linked_cels(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    before = source.read_bytes()
    code, result = run(
        "tilemap",
        "set",
        **files(source, target),
        snapshot={
            "coordinate_space": "tile-cell",
            "rectangle": {"x": 1, "y": 0, "width": 3, "height": 1},
            "complete": True,
            "default": {"kind": "empty"},
            "entries": [
                {"tile_x": 2, "tile_y": 0, "placement": placement("b", flip_y=True)}
            ],
        },
    )
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    assert result["cells_written"] == 3
    assert result["cells_changed"] == 3
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1, 2]
    assert source.read_bytes() == before
    fixture(
        target, runtime, script="verify_lifecycle.lua", order=json.dumps([1, 2, 3, 4])
    )
    for frame in (1, 2):
        code, observed = run(
            "tilemap",
            "get",
            sprite_file=str(target),
            target={"layer": {"layer_name": "map"}, "frame_number": frame},
            rectangle={"x": 0, "y": 0, "width": 5, "height": 1},
        )
        assert code == 0, observed
        assert observed["tilemap"]["position"] == {"x": -3, "y": 7}
        entries = observed["snapshot"]["entries"]
        assert [entry["tile_x"] for entry in entries] == [0, 2, 4]
        assert entries[1]["placement"] == placement("b", flip_y=True) | {
            "tile_index": 2
        }
        assert entries[-1]["placement"]["tile_index"] == 0
        assert entries[-1]["placement"]["tile_key"] is None
        assert result["affected_cels"][frame - 1]["linked_cels"] == [
            {"layer_path": [2], "frame_number": 3 - frame}
        ]


def test_patch_changes_only_explicit_cells(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    code, result = run(
        "tilemap",
        "patch",
        **files(source, target, frame=2),
        patch={
            "coordinate_space": "tile-cell",
            "entries": [
                {"tile_x": 4, "tile_y": 0, "placement": placement("a", flip_x=True)},
                {"tile_x": 2, "tile_y": 0, "placement": {"kind": "empty"}},
            ],
        },
    )
    assert code == 0, result
    assert result["cells_written"] == result["cells_changed"] == 2
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target={"layer": {"layer_name": "map"}, "frame_number": 1},
        rectangle={"x": 0, "y": 0, "width": 5, "height": 1},
    )
    assert code == 0, observed
    entries = observed["snapshot"]["entries"]
    assert [entry["tile_x"] for entry in entries] == [0, 1, 3, 4]
    assert entries[-1]["placement"] == placement("a", flip_x=True) | {"tile_index": 1}
    assert entries[1]["placement"] == placement(
        "b", flip_x=True, flip_y=True, flip_diagonal=True
    ) | {"tile_index": 2}


@pytest.mark.parametrize("mode", ["rgb", "grayscale"])
@pytest.mark.parametrize(
    "flags",
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
    ],
)
def test_fill_one_placement_and_empty_whole_image(
    tmp_path: Path, runtime, mode: str, flags: tuple
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode=mode)
    value = placement("d", flip_x=flags[0], flip_y=flags[1], flip_diagonal=flags[2])
    rectangle = {"x": 0, "y": 0, "width": 5, "height": 1}
    code, result = run(
        "tilemap",
        "fill",
        **files(source, target),
        coordinate_space="tile-cell",
        rectangle=rectangle,
        placement=value,
    )
    assert code == 0, result
    assert result["cells_written"] == 5
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target=files(source, target)["target"],
        rectangle=rectangle,
    )
    assert code == 0, observed
    assert [entry["placement"] for entry in observed["snapshot"]["entries"]] == [
        value | {"tile_index": 4}
    ] * 5
    code, result = run(
        "tilemap",
        "fill",
        **files(target, target, in_place=True, overwrite=True),
        coordinate_space="tile-cell",
        rectangle=rectangle,
        placement={"kind": "empty"},
    )
    assert code == 0, result
    assert result["cells_changed"] == 5
    assert result["tilemap"]["cell_size"] == {"width": 5, "height": 1}
    assert result["tilemap"]["position"] == {"x": -3, "y": 7}
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target=files(source, target)["target"],
        rectangle=rectangle,
    )
    assert code == 0 and observed["snapshot"]["entries"] == [], observed


def test_indexed_write_validates_linked_frame_not_tile_creation_basis(
    tmp_path: Path, runtime
) -> None:
    from tests.support import inject_palette_change
    from tests.tile.support import snapshot

    source, keyed, target = (
        tmp_path / name
        for name in ("source.aseprite", "keyed.aseprite", "target.aseprite")
    )
    fixture(source, runtime, script="lifecycle.lua", mode="indexed", palette_size=10)
    image = snapshot("indexed")
    for row in image["rows"]:
        row[0]["color"]["index"] = 9
    code, added = run(
        "tileset",
        "tile",
        "add",
        source_sprite_file=str(source),
        target_sprite_file=str(keyed),
        in_place=False,
        overwrite=False,
        target={"tileset_index": 1},
        tile_key="new",
        image=image,
        palette_frame_number=1,
    )
    assert code == 0, json.dumps(added, indent=2)
    assert added["effective_palette"]["frame_number"] == 1
    inject_palette_change(
        keyed, [(20 + i, 40, 60, 255) for i in range(8)], frame_number=2
    )
    before = keyed.read_bytes()
    target.write_bytes(b"prior Target")
    code, refused = run(
        "tilemap",
        "fill",
        **files(keyed, target, overwrite=True),
        coordinate_space="tile-cell",
        rectangle={"x": 0, "y": 0, "width": 1, "height": 1},
        placement=placement("new"),
    )
    assert code == 2, refused
    assert refused["code"] == "tilemap_region_invalid"
    assert refused["details"]["reason"] == "palette_incompatible"
    assert refused["details"]["frame_number"] == 2
    assert refused["details"]["palette_frame_number"] == 2
    assert refused["details"]["undefined_indexes"] == [9]
    assert keyed.read_bytes() == before
    assert target.read_bytes() == b"prior Target"


def test_indexed_write_reports_different_valid_frame_palettes_without_remap(
    tmp_path: Path, runtime
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode="indexed", palette_size=8)
    inject_palette_change(
        source, [(20 + i, 40, 60, 255) for i in range(8)], frame_number=2
    )
    code, result = run(
        "tilemap",
        "patch",
        **files(source, target, frame=2),
        patch={
            "entries": [
                {"tile_x": 0, "tile_y": 0, "placement": placement("d")},
            ]
        },
    )
    assert code == 0, json.dumps(result, indent=2)
    assert result["written_tiles"] == [
        {"tile_key": "d", "tile_index": 4, "palette_indexes": [4]}
    ]
    facts = result["effective_palettes"]
    assert [
        (f["frame_number"], f["palette_frame_number"], f["palette_size"]) for f in facts
    ] == [(1, 1, 8), (2, 2, 8)]
    assert all(
        [entry["index"] for entry in fact["indexes"]] == [4, 7] for fact in facts
    )
    assert facts[0]["indexes"][0]["color"] != facts[1]["indexes"][0]["color"]
    assert facts[1]["indexes"][0]["color"] == {
        "red": 24,
        "green": 40,
        "blue": 60,
        "alpha": 255,
    }
    code, tile = run(
        "tileset",
        "tile",
        "get",
        sprite_file=str(target),
        target={"tileset_index": 1},
        tile={"tile_key": "d"},
    )
    assert code == 0, tile
    assert all(
        row == [{"length": 2, "color": {"kind": "palette-index", "index": 4}}]
        for row in tile["snapshot"]["rows"]
    )


@pytest.mark.parametrize(
    "operation,inputs",
    [
        (
            "set",
            {
                "snapshot": {
                    "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                    "entries": [
                        {"tile_x": 0, "tile_y": 0, "placement": placement("a")}
                    ],
                }
            },
        ),
        (
            "patch",
            {
                "patch": {
                    "entries": [{"tile_x": 0, "tile_y": 0, "placement": placement("a")}]
                }
            },
        ),
        (
            "fill",
            {
                "coordinate_space": "tile-cell",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                "placement": placement("a"),
            },
        ),
    ],
)
def test_transparent_index_is_required_even_when_tile_does_not_use_it(
    tmp_path: Path, runtime, operation: str, inputs: dict
) -> None:
    from tests.support import inject_palette_change

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode="indexed", palette_size=8)
    inject_palette_change(source, [(i, 40, 60, 255) for i in range(3)], frame_number=2)
    before = source.read_bytes()
    code, result = run("tilemap", operation, **files(source, target), **inputs)
    assert code == 2, result
    assert result["details"]["undefined_indexes"] == [7]
    assert result["details"]["frame_number"] == 2
    assert source.read_bytes() == before and not target.exists()


@pytest.mark.parametrize("frame", [1, 3])
def test_explicit_cel_creation_composes_with_keyed_set(
    tmp_path: Path, runtime, frame: int
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="cel_creation.lua")
    arguments = files(source, target, frame=frame)
    code, added = run("cel", "add", **arguments, tilemap_size={"width": 2, "height": 3})
    assert code == 0, added
    code, changed = run(
        "tilemap",
        "set",
        **files(target, target, frame=frame, in_place=True, overwrite=True),
        snapshot={
            "rectangle": {"x": 0, "y": 0, "width": 2, "height": 3},
            "entries": [
                {
                    "tile_x": 1,
                    "tile_y": 2,
                    "placement": placement("stone", flip_diagonal=True),
                }
            ],
        },
    )
    assert code == 0, changed
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target=arguments["target"],
        rectangle={"x": 0, "y": 0, "width": 2, "height": 3},
    )
    assert code == 0, observed
    assert observed["snapshot"]["entries"] == [
        {
            "tile_x": 1,
            "tile_y": 2,
            "placement": placement("stone", flip_diagonal=True) | {"tile_index": 1},
        }
    ]


@pytest.mark.parametrize(
    "operation,inputs,fixture_options,expected",
    [
        (
            "set",
            {
                "snapshot": {
                    "rectangle": {"x": 4, "y": 0, "width": 2, "height": 1},
                    "entries": [],
                }
            },
            {},
            "tile_region_out_of_bounds",
        ),
        (
            "set",
            {
                "snapshot": {
                    "rectangle": {"x": 0, "y": 0, "width": 5, "height": 1},
                    "entries": [
                        {"tile_x": 0, "tile_y": 0, "placement": placement("missing")}
                    ],
                }
            },
            {},
            "tile_key_missing",
        ),
        (
            "patch",
            {
                "patch": {
                    "entries": [
                        {"tile_x": 0, "tile_y": 0, "placement": placement("a")},
                        {"tile_x": 5, "tile_y": 0, "placement": {"kind": "empty"}},
                    ]
                }
            },
            {},
            "tile_region_out_of_bounds",
        ),
        (
            "patch",
            {
                "patch": {
                    "entries": [
                        {
                            "tile_x": 0,
                            "tile_y": 2**53 + 1,
                            "placement": {"kind": "empty"},
                        }
                    ]
                }
            },
            {},
            "tile_region_out_of_bounds",
        ),
        (
            "patch",
            {
                "patch": {
                    "entries": [
                        {"tile_x": 0, "tile_y": 0, "placement": placement("d")},
                        {"tile_x": 1, "tile_y": 0, "placement": placement("absent")},
                    ]
                }
            },
            {},
            "tile_key_missing",
        ),
        (
            "fill",
            {
                "coordinate_space": "tile-cell",
                "rectangle": {"x": 0, "y": 0, "width": 2**53 + 1, "height": 1},
                "placement": {"kind": "empty"},
            },
            {},
            "tile_region_out_of_bounds",
        ),
        (
            "fill",
            {
                "coordinate_space": "tile-cell",
                "rectangle": {"x": -1, "y": 0, "width": 1, "height": 1},
                "placement": {"kind": "empty"},
            },
            {},
            "tile_region_out_of_bounds",
        ),
        (
            "fill",
            {
                "coordinate_space": "tile-cell",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                "placement": placement("a"),
            },
            {"duplicate": "4"},
            "tile_key_ambiguous",
        ),
    ],
)
def test_rejected_region_preserves_source_and_existing_target(
    tmp_path: Path,
    runtime,
    operation: str,
    inputs: dict,
    fixture_options: dict,
    expected: str,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", **fixture_options)
    before = source.read_bytes()
    target.write_bytes(b"prior Target")
    code, result = run(
        "tilemap", operation, **files(source, target, overwrite=True), **inputs
    )
    assert code == 2 and result["code"] == expected, result
    assert source.read_bytes() == before
    assert target.read_bytes() == b"prior Target"
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.parametrize(
    "operation,inputs",
    [
        (
            "set",
            {
                "snapshot": {
                    "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                    "entries": [],
                }
            },
        ),
        ("patch", {"patch": {"entries": []}}),
        (
            "fill",
            {
                "coordinate_space": "tile-cell",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                "placement": {"kind": "empty"},
            },
        ),
    ],
)
def test_absent_cel_stays_absent_in_summary_and_cannot_be_mutated(
    tmp_path: Path, runtime, operation: str, inputs: dict
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="cel_creation.lua")
    before = source.read_bytes()
    code, result = run(
        "tilemap",
        "get",
        sprite_file=str(source),
        target=files(source, target)["target"],
    )
    assert code == 0 and result["tilemap"]["exists"] is False, result
    code, result = run("tilemap", operation, **files(source, target), **inputs)
    assert code == 2 and result["code"] == "tilemap_cel_missing", result
    code, result = run(
        "tilemap",
        "get",
        sprite_file=str(source),
        target=files(source, target)["target"],
        rectangle={"x": 0, "y": 0, "width": 1, "height": 1},
    )
    assert code == 2 and result["code"] == "tilemap_cel_missing", result
    assert source.read_bytes() == before and not target.exists()


def test_empty_and_noop_patches_do_not_repair_unrelated_placements(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", unkeyed="3", invalid="true")
    code, result = run(
        "tilemap", "patch", **files(source, target), patch={"entries": []}
    )
    assert code == 0, result
    assert result["cells_written"] == result["cells_changed"] == 0
    assert result["written_tiles"] == result["effective_palettes"] == []
    code, observed = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target=files(source, target)["target"],
        rectangle={"x": 0, "y": 0, "width": 5, "height": 1},
    )
    assert code == 0, observed
    assert observed["snapshot"]["entries"][0]["placement"]["tile_index"] == 99
    assert observed["snapshot"]["entries"][2]["placement"]["tile_key"] is None
    code, result = run(
        "tilemap",
        "patch",
        **files(target, target, in_place=True, overwrite=True),
        patch={
            "entries": [
                {
                    "tile_x": 1,
                    "tile_y": 0,
                    "placement": placement(
                        "b", flip_x=True, flip_y=True, flip_diagonal=True
                    ),
                }
            ]
        },
    )
    assert (
        code == 0 and result["cells_written"] == 1 and result["cells_changed"] == 0
    ), result


@pytest.mark.parametrize(
    "defect",
    [
        "target",
        "affected",
        "links",
        "counts",
        "geometry",
        "tile-index",
        "palette-frame",
        "palette-index",
    ],
)
def test_contradictory_region_evidence_never_publishes(
    tmp_path: Path, runtime, defect: str
) -> None:
    from spa.adapters.aseprite.aseprite import invoke
    from spa.adapters.files import LocalTargetFiles
    from spa.authoring.tile.regions import TilemapFillRequest, fill_tilemap
    from spa.contracts.ports import (
        KernelInvocationResult,
        OperationServices,
        RuntimeIssue,
    )

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode="indexed", palette_size=8)
    before = source.read_bytes()
    target.write_bytes(b"prior Target")
    request = TilemapFillRequest.model_validate(
        files(source, target, overwrite=True)
        | {
            "coordinate_space": "tile-cell",
            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
            "placement": placement("a"),
        }
    )

    def corrupt(observation, handler, payload, timeout):
        invocation = invoke(observation, handler, payload, timeout)
        evidence = invocation.payload
        if defect == "target":
            evidence["tilemap"]["frame_number"] = 2
        elif defect == "affected":
            evidence["affected_cels"].pop()
        elif defect == "links":
            evidence["affected_cels"][0]["linked_cels"] = []
        elif defect == "counts":
            evidence["cells_written"] = 2
        elif defect == "geometry":
            evidence["tilemap"]["cell_size"]["width"] = 99
        elif defect == "tile-index":
            evidence["written_tiles"][0]["tile_index"] = 999
        elif defect == "palette-frame":
            evidence["effective_palettes"].pop()
        else:
            evidence["effective_palettes"][0]["indexes"].pop()
        return KernelInvocationResult(
            evidence, invocation.response_path, invocation.diagnostics
        )

    services = OperationServices(
        probe_runtime=lambda _: runtime,
        invoke_kernel=corrupt,
        target_files=LocalTargetFiles(),
    )
    with pytest.raises(RuntimeIssue) as caught:
        fill_tilemap(request, services)
    assert caught.value.kind == "response_malformed"
    assert source.read_bytes() == before and target.read_bytes() == b"prior Target"
    assert set(tmp_path.iterdir()) == {source, target}


def test_native_save_failure_rolls_back_file_publication(
    tmp_path: Path, runtime
) -> None:
    from spa.adapters.aseprite.aseprite import invoke
    from spa.adapters.files import LocalTargetFiles
    from spa.authoring.tile.regions import TilemapFillRequest, fill_tilemap
    from spa.contracts.ports import OperationServices, RuntimeIssue

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    before = source.read_bytes()
    target.write_bytes(b"prior Target")
    request = TilemapFillRequest.model_validate(
        files(source, target, overwrite=True)
        | {
            "coordinate_space": "tile-cell",
            "rectangle": {"x": 0, "y": 0, "width": 5, "height": 1},
            "placement": {"kind": "empty"},
        }
    )

    def fail_save(observation, handler, payload, timeout):
        # The real Kernel performs the mutation, then native save cannot create this path.
        return invoke(
            observation,
            handler,
            payload | {"staged_sprite_file": str(source / "stage.aseprite")},
            timeout,
        )

    services = OperationServices(
        probe_runtime=lambda _: runtime,
        invoke_kernel=fail_save,
        target_files=LocalTargetFiles(),
    )
    with pytest.raises(RuntimeIssue) as caught:
        fill_tilemap(request, services)
    assert caught.value.kind == "handler_rejected"
    assert source.read_bytes() == before and target.read_bytes() == b"prior Target"
    assert set(tmp_path.iterdir()) == {source, target}


def test_whole_image_limit_is_explicit_even_for_one_cell_write(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(
        source,
        runtime,
        script="lifecycle_limits.lua",
        tile_count=2,
        frames=1,
        image_width=2049,
    )
    before = source.read_bytes()
    code, result = run(
        "tilemap",
        "fill",
        **files(
            source, target, target={"layer": {"layer_path": [2]}, "frame_number": 1}
        ),
        coordinate_space="tile-cell",
        rectangle={"x": 0, "y": 0, "width": 1, "height": 1},
        placement={"kind": "empty"},
    )
    assert code == 2 and result["code"] == "tilemap_region_invalid", result
    assert result["details"]["reason"] == "tile_cells_limit"
    assert source.read_bytes() == before and not target.exists()
