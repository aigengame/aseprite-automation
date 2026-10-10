"""Keyed Tile lifecycle through the public SPA interface and persisted native data."""

import json
from pathlib import Path

import pytest

from tests.support import clear_first_saved_layer_uuid, inject_palette_change
from tests.tile.support import fixture, run, snapshot

pytestmark = pytest.mark.e2e


def files(source: Path, destination: Path, **extra: object) -> dict:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(destination),
        "in_place": source == destination,
        "overwrite": source == destination,
        "target": {"tileset_index": 1},
        **extra,
    }


def test_add_appends_explicit_complete_image_and_key(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "added.aseprite"
    fixture(source, runtime)
    original = source.read_bytes()
    image = snapshot()
    code, added = run(
        "tileset", "tile", "add", **files(source, target), tile_key="new", image=image
    )
    assert code == 0, added
    assert added["tile"] == {"tile_index": 5, "tile_key": "new"}
    assert added["persisted_reopen_verified"] is True
    assert added["affected_cels"] == []
    code, observed = run(
        "tileset",
        "tile",
        "get",
        sprite_file=str(target),
        target={"tileset_index": 1},
        tile={"tile_key": "new"},
    )
    assert code == 0, observed
    assert observed["snapshot"] == image
    assert source.read_bytes() == original


def test_assign_missing_key_preserves_native_metadata(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "keyed.aseprite"
    fixture(source, runtime, script="lifecycle.lua", unkeyed="3")
    original = source.read_bytes()
    code, assigned = run(
        "tileset",
        "tile",
        "assign-key",
        **files(source, target),
        tile_index=3,
        tile_key="c",
    )
    assert code == 0, assigned
    assert assigned["tile"] == {"tile_index": 3, "tile_key": "c"}
    assert assigned["affected_cels"] == []
    fixture(
        target, runtime, script="verify_lifecycle.lua", order=json.dumps([1, 2, 3, 4])
    )
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "replacement,order,cells",
    [
        ({"kind": "empty"}, [1, 3, 4], [1, None, 2, 3]),
        ({"kind": "tile", "tile_key": "d"}, [1, 3, 4], [1, 3, 2, 3]),
        ({"kind": "tile", "tile_key": "a"}, [1, 3, 4], [1, 1, 2, 3]),
    ],
)
def test_remove_maps_all_linked_and_shared_placements(
    tmp_path: Path, runtime, replacement: dict, order: list, cells: list
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "removed.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    original = source.read_bytes()
    code, removed = run(
        "tileset",
        "tile",
        "remove",
        **files(source, target),
        tile_key="b",
        replacement=replacement,
    )
    assert code == 0, removed
    assert len(removed["affected_cels"]) == 3
    assert len(removed["affected_layers"]) == 2
    assert [item["new_index"] for item in removed["index_mapping"]] == [
        0,
        1,
        cells[1] or 0,
        2,
        3,
    ]
    packed = [0 if index is None else index | 0xE0000000 for index in cells] + [
        0xE0000000
    ]
    fixture(
        target,
        runtime,
        script="verify_lifecycle.lua",
        order=json.dumps(order),
        cells=json.dumps(packed),
    )
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "keys,order,mapping,changed",
    [
        pytest.param(
            ["a", "b", "c", "d"], [1, 2, 3, 4], [0, 1, 2, 3, 4], 0, id="original"
        ),
        pytest.param(
            ["d", "c", "b", "a"], [4, 3, 2, 1], [0, 4, 3, 2, 1], 4, id="reverse"
        ),
        pytest.param(
            ["d", "b", "a", "c"], [4, 2, 1, 3], [0, 3, 2, 4, 1], 3, id="mixed"
        ),
    ],
)
def test_reorder_preserves_keys_images_flags_and_native_properties(
    tmp_path: Path, runtime, keys: list, order: list, mapping: list, changed: int
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "reordered.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    original = source.read_bytes()
    code, result = run(
        "tileset",
        "tile",
        "reorder",
        **files(source, target),
        tile_keys=keys,
    )
    assert code == 0, result
    assert [item["new_index"] for item in result["index_mapping"]] == mapping
    assert [item["changed_cells"] for item in result["affected_cels"]] == (
        [changed] * 3 if changed else []
    )
    fixture(
        target,
        runtime,
        script="verify_lifecycle.lua",
        order=json.dumps(order),
        cells=json.dumps([index | 0xE0000000 for index in [*mapping[1:], 0]]),
    )
    assert source.read_bytes() == original


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("transparent", [False, True])
def test_add_preserves_complete_pixels_in_each_mode(
    tmp_path: Path, runtime, mode: str, transparent: bool
) -> None:
    source = tmp_path / "source.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode=mode, base_index="-32768")
    if mode == "indexed":
        inject_palette_change(
            source, [((20 + i) % 256, 40, 60, 255) for i in range(256)], frame_number=2
        )
    image = snapshot(mode, transparent=transparent)
    extra = {"palette_frame_number": 2} if mode == "indexed" else {}
    code, added = run(
        "tileset",
        "tile",
        "add",
        **files(source, source),
        tile_key="new",
        image=image,
        **extra,
    )
    assert code == 0, added
    assert added["tile"] == {"tile_index": 5, "tile_key": "new"}
    assert added["tileset"]["base_index"] == -32768
    if mode == "indexed":
        basis = added["effective_palette"]
        assert basis["frame_number"] == basis["palette_frame_number"] == 2
        assert added["transparent_index"] == 7
        assert basis["indexes"] == [
            {
                "index": 7 if transparent else 2,
                "color": {
                    "red": 27 if transparent else 22,
                    "green": 40,
                    "blue": 60,
                    "alpha": 255,
                },
            }
        ]
    code, observed = run(
        "tileset",
        "tile",
        "get",
        sprite_file=str(source),
        target={"tileset_index": 1},
        tile={"tile_key": "new"},
    )
    assert code == 0, observed
    assert observed["snapshot"] == image


@pytest.mark.parametrize(
    "operation,inputs,fixture_options,expected",
    [
        ("add", {"tile_key": "a", "image": snapshot()}, {}, "tile_lifecycle_invalid"),
        (
            "add",
            {"tile_key": "new", "image": snapshot("grayscale")},
            {},
            "tile_lifecycle_invalid",
        ),
        (
            "assign-key",
            {"tile_index": 3, "tile_key": "a"},
            {"unkeyed": "3"},
            "tile_lifecycle_invalid",
        ),
        (
            "assign-key",
            {"tile_index": 1, "tile_key": "new"},
            {},
            "tile_lifecycle_invalid",
        ),
        ("assign-key", {"tile_index": 0, "tile_key": "new"}, {}, "invalid_request"),
        (
            "assign-key",
            {"tile_index": 2**53 + 1, "tile_key": "new"},
            {},
            "tile_index_out_of_bounds",
        ),
        ("remove", {"tile_key": "a"}, {}, "tile_lifecycle_invalid"),
        ("remove", {"tile_key": "absent"}, {}, "tile_key_missing"),
        (
            "remove",
            {"tile_key": "a", "replacement": {"kind": "tile", "tile_key": "a"}},
            {},
            "tile_lifecycle_invalid",
        ),
        (
            "remove",
            {"tile_key": "a", "replacement": {"kind": "empty"}},
            {"duplicate": "4"},
            "tile_key_ambiguous",
        ),
        (
            "remove",
            {"tile_key": "a", "replacement": {"kind": "empty"}},
            {"invalid": "true"},
            "tile_lifecycle_invalid",
        ),
        ("reorder", {"tile_keys": ["a", "b", "c"]}, {}, "tile_lifecycle_invalid"),
        (
            "reorder",
            {"tile_keys": ["a", "b", "c", "extra"]},
            {},
            "tile_lifecycle_invalid",
        ),
        ("reorder", {"tile_keys": ["a", "b", "c", "c"]}, {}, "invalid_request"),
        (
            "reorder",
            {"tile_keys": ["d", "c", "b", "a"]},
            {"unkeyed": "3"},
            "tile_lifecycle_invalid",
        ),
        (
            "reorder",
            {"tile_keys": ["d", "c", "b", "a"]},
            {"duplicate": "4"},
            "tile_lifecycle_invalid",
        ),
    ],
)
def test_refusal_preserves_source_existing_target_and_cleans_staging(
    tmp_path: Path,
    runtime,
    operation: str,
    inputs: dict,
    fixture_options: dict,
    expected: str,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", **fixture_options)
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    code, refused = run(
        "tileset", "tile", operation, **files(source, target, overwrite=True), **inputs
    )
    assert code == 2, refused
    assert refused["code"] == expected
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.parametrize(
    "frame,index,palette_size", [(3, 2, 8), (2**53 + 1, 2, 8), (1, 9, 8), (2, 1, 2)]
)
def test_add_rejects_invalid_palette_basis(
    tmp_path: Path, runtime, frame: int, index: int, palette_size: int
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode="indexed")
    inject_palette_change(
        source,
        [(i, 20, 30, 255) for i in range(palette_size)],
        frame_number=2 if palette_size == 2 else 1,
    )
    image = snapshot("indexed")
    for row in image["rows"]:
        row[0]["color"]["index"] = index
    original = source.read_bytes()
    code, failure = run(
        "tileset",
        "tile",
        "add",
        **files(source, target),
        tile_key="new",
        image=image,
        palette_frame_number=frame,
    )
    assert code == 2, failure
    assert failure["code"] == "tile_lifecycle_invalid"
    assert failure["details"]["reason"] in {"palette_frame", "palette_index"}
    assert source.read_bytes() == original
    assert not target.exists()


def test_unused_removal_needs_no_replacement(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", unused="4")
    code, result = run(
        "tileset", "tile", "remove", **files(source, target), tile_key="d"
    )
    assert code == 0, result
    assert result["replacement"] is None
    assert result["affected_cels"] == []
    fixture(
        target,
        runtime,
        script="verify_lifecycle.lua",
        order=json.dumps([1, 2, 3]),
        cells=json.dumps(
            [1 | 0xE0000000, 2 | 0xE0000000, 3 | 0xE0000000, 0, 0xE0000000]
        ),
    )


def test_orphan_reorder_leaves_no_temporary_native_objects(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    code, before = run(
        "sprite",
        "get",
        sprite_file=str(source),
        inspection_scope=["frames", "layers", "cels", "tilesets"],
    )
    assert code == 0, before
    code, result = run(
        "tileset",
        "tile",
        "reorder",
        **files(source, target, target={"tileset_name": "orphan"}),
        tile_keys=["y", "x"],
    )
    assert code == 0, result
    assert result["affected_layers"] == result["affected_cels"] == []
    assert [tile["tile_key"] for tile in result["tiles"]] == [None, "y", "x"]
    fixture(
        target,
        runtime,
        script="verify_lifecycle.lua",
        order=json.dumps([1, 2, 3, 4]),
        orphan_order=json.dumps([2, 1]),
        cells=json.dumps([index | 0xE0000000 for index in [1, 2, 3, 4, 0]]),
    )
    code, after = run(
        "sprite",
        "get",
        sprite_file=str(target),
        inspection_scope=["frames", "layers", "cels", "tilesets"],
    )
    assert code == 0, after
    assert {
        key: before[key] for key in ["metadata", "frames", "layers", "cels", "tilesets"]
    } == {
        key: after[key] for key in ["metadata", "frames", "layers", "cels", "tilesets"]
    }


def test_reorder_reports_persisted_layer_uuids(tmp_path: Path, runtime) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", uuids="true")
    clear_first_saved_layer_uuid(source, "map")
    code, result = run(
        "tileset",
        "tile",
        "reorder",
        **files(source, target),
        tile_keys=["d", "c", "b", "a"],
    )
    assert code == 0, result
    assert result["before_tileset"]["layers"][0]["layer_uuid"] is None
    assert result["tileset"]["layers"][0]["layer_uuid"] is not None
    assert result["affected_layers"] == result["tileset"]["layers"]


@pytest.mark.parametrize("defect", ["mapping", "image", "order", "palette", "tileset"])
def test_contradictory_native_evidence_never_publishes_target(
    tmp_path: Path, runtime, defect: str
) -> None:
    from spa.adapters.aseprite.aseprite import invoke
    from spa.adapters.files import LocalTargetFiles
    from spa.authoring.tile.lifecycle import TileAddRequest, add_tile
    from spa.contracts.ports import (
        KernelInvocationResult,
        OperationServices,
        RuntimeIssue,
    )

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    request = TileAddRequest.model_validate(
        files(source, target, overwrite=True) | {"tile_key": "new", "image": snapshot()}
    )

    def corrupt(observation, handler, payload, timeout):
        result = invoke(observation, handler, payload, timeout)
        evidence = result.payload
        if defect == "mapping":
            evidence["index_mapping"][1]["new_index"] = 2
        elif defect == "image":
            evidence["image_content_digest"]["value"] = "0" * 16
        elif defect == "order":
            evidence["tiles"][1]["tile_key"] = "wrong"
        elif defect == "palette":
            evidence["transparent_index"] = 0
        else:
            evidence["sprite"]["tilesets"][0]["tile_count"] = 1
        return KernelInvocationResult(
            evidence, result.response_path, result.diagnostics
        )

    services = OperationServices(
        probe_runtime=lambda _: runtime,
        invoke_kernel=corrupt,
        target_files=LocalTargetFiles(),
    )
    with pytest.raises(RuntimeIssue) as caught:
        add_tile(request, services)
    assert caught.value.kind == "response_malformed"
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"
    assert set(tmp_path.iterdir()) == {source, target}


def test_changed_cell_count_uses_tile_cells_before_publication(
    tmp_path: Path, runtime
) -> None:
    from spa.adapters.aseprite.aseprite import invoke
    from spa.adapters.files import LocalTargetFiles
    from spa.authoring.tile.lifecycle import TileReorderRequest, reorder_tiles
    from spa.contracts.ports import (
        KernelInvocationResult,
        OperationServices,
        RuntimeIssue,
    )

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua")
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    request = TileReorderRequest.model_validate(
        files(source, target, overwrite=True) | {"tile_keys": ["d", "c", "b", "a"]}
    )

    def corrupt(observation, handler, payload, timeout):
        result = invoke(observation, handler, payload, timeout)
        evidence = result.payload
        assert evidence["affected_cels"][0]["changed_cells"] == 4
        # The fixture has five Cells with 2x3-pixel Tiles, not thirty Cells.
        evidence["affected_cels"][0]["changed_cells"] = 6
        return KernelInvocationResult(
            evidence, result.response_path, result.diagnostics
        )

    services = OperationServices(
        probe_runtime=lambda _: runtime,
        invoke_kernel=corrupt,
        target_files=LocalTargetFiles(),
    )
    with pytest.raises(RuntimeIssue) as caught:
        reorder_tiles(request, services)
    assert caught.value.kind == "response_malformed"
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.parametrize("mode", ["rgb", "grayscale"])
def test_hidden_channel_input_is_explicitly_refused_before_mutation(
    tmp_path: Path, runtime, mode: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle.lua", mode=mode)
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    image = snapshot(mode)
    for row in image["rows"]:
        row[0]["color"]["alpha"] = 0
    code, result = run(
        "tileset",
        "tile",
        "add",
        **files(source, target, overwrite=True),
        tile_key="new",
        image=image,
    )
    assert code == 2, result
    assert result["code"] == "tile_lifecycle_invalid"
    assert result["details"]["reason"] == "image_incompatible"
    assert "hidden" in result["message"]
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.parametrize("width,height", [(64, 64), (4097, 1)])
def test_add_inline_pixel_limit_counts_pixels_in_compressed_runs(
    tmp_path: Path, runtime, width: int, height: int
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle_limits.lua", width=width, height=height)
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    image = snapshot()
    color = image["rows"][0][0]["color"]
    image["rectangle"].update(width=width, height=height)
    image["rows"] = [[{"length": width, "color": color}] for _ in range(height)]
    code, result = run(
        "tileset",
        "tile",
        "add",
        **files(source, target, overwrite=True),
        tile_key="new",
        image=image,
    )
    if width * height == 4096:
        assert code == 0, result
        assert result["tile"] == {"tile_index": 1, "tile_key": "new"}
        code, observed = run(
            "tileset",
            "tile",
            "get",
            sprite_file=str(target),
            target={"tileset_index": 1},
            tile={"tile_key": "new"},
        )
        assert code == 0, observed
        assert observed["snapshot"] == image
    else:
        assert code == 2, result
        assert result["code"] == "tile_lifecycle_invalid"
        assert result["details"]["reason"] == "operation_limit"
        assert result["details"]["limit"] == {
            "unit": "image_pixels",
            "requested": 4097,
            "maximum": 4096,
        }
        assert target.read_bytes() == b"previous target"
    assert source.read_bytes() == original
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.parametrize(
    "operation,count,accepted",
    [
        ("add", 4095, True),
        ("add", 4096, False),
        ("assign-key", 4096, True),
        ("assign-key", 4097, False),
        ("remove", 4097, False),
        ("reorder", 4096, True),
        ("reorder", 4097, False),
    ],
)
def test_tile_count_limit_includes_empty_and_append_result(
    tmp_path: Path, runtime, operation: str, count: int, accepted: bool
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(
        source,
        runtime,
        script="lifecycle_limits.lua",
        tile_count=count,
        unkeyed=1 if operation == "assign-key" else 0,
    )
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    image = snapshot()
    image["rectangle"].update(width=1, height=1)
    image["rows"] = [[{"length": 1, "color": image["rows"][0][0]["color"]}]]
    parameters = {
        "add": {"tile_key": "new", "image": image},
        "assign-key": {"tile_index": 1, "tile_key": "new"},
        "remove": {"tile_key": "tile-2"},
        "reorder": {"tile_keys": [f"tile-{index}" for index in range(1, count)]},
    }[operation]
    # The accepted 4096-Tile permutation can exceed 15 seconds under parallel load.
    code, result = run(
        "tileset",
        "tile",
        operation,
        **files(source, target, overwrite=True),
        timeout_seconds=60,
        **parameters,
    )
    if accepted:
        assert code == 0, result
        assert result["tileset"]["tile_count"] == 4096
        assert len(result["index_mapping"]) == count
        if operation == "reorder":
            assert [tile["tile_key"] for tile in result["tiles"]] == [
                None,
                *parameters["tile_keys"],
            ]
        else:
            assert result["tile"]["tile_key"] == "new"
    else:
        assert code == 2, result
        assert result["code"] == "tile_lifecycle_invalid"
        assert result["details"]["reason"] == "operation_limit"
        assert result["details"]["limit"] == {
            "unit": "tiles",
            "requested": 4097,
            "maximum": 4096,
        }
        assert target.read_bytes() == b"previous target"
    assert source.read_bytes() == original
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.parametrize("order", ["reverse", "mixed"])
def test_reorder_permutations_at_tile_count_limit(
    tmp_path: Path, runtime, order: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="lifecycle_limits.lua", tile_count=4096)
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    keys = [f"tile-{index}" for index in range(1, 4096)]
    requested = keys[::-1] if order == "reverse" else keys[::2] + keys[1::2]
    code, result = run(
        "tileset",
        "tile",
        "reorder",
        **files(source, target, overwrite=True),
        tile_keys=requested,
        timeout_seconds=60,
    )
    assert code == 0, result
    assert result["tileset"]["tile_count"] == 4096
    assert [tile["tile_key"] for tile in result["tiles"]] == [None, *requested]
    expected_indexes = {key: index for index, key in enumerate(requested, start=1)}
    assert result["index_mapping"] == [
        {"old_index": 0, "new_index": 0, "tile_key": None},
        *[
            {"old_index": index, "new_index": expected_indexes[key], "tile_key": key}
            for index, key in enumerate(keys, start=1)
        ],
    ]
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.parametrize("operation", ["remove", "reorder"])
@pytest.mark.parametrize("frames,peer", [(2, False), (3, False), (2, True)])
def test_referenced_cell_limit_counts_linked_empty_unchanged_cels(
    tmp_path: Path, runtime, operation: str, frames: int, peer: bool
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(
        source,
        runtime,
        script="lifecycle_limits.lua",
        tile_count=3,
        frames=frames,
        **({"peer": "true"} if peer else {}),
    )
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    parameters = (
        {"tile_key": "tile-1"}
        if operation == "remove"
        else {"tile_keys": ["tile-1", "tile-2"]}
    )
    code, result = run(
        "tileset",
        "tile",
        operation,
        **files(source, target, overwrite=True),
        **parameters,
    )
    if frames == 2 and not peer:
        assert code == 0, result
        assert result["affected_cels"] == []
        assert result["tileset"]["tile_count"] == (2 if operation == "remove" else 3)
    else:
        assert code == 2, result
        assert result["code"] == "tile_lifecycle_invalid"
        assert result["details"]["reason"] == "operation_limit"
        assert result["details"]["limit"] == {
            "unit": "tile_cells",
            "requested": 1_572_864,
            "maximum": 1_048_576,
        }
        assert target.read_bytes() == b"previous target"
    assert source.read_bytes() == original
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.parametrize("operation", ["add", "assign-key"])
def test_non_remapping_operations_do_not_apply_the_referenced_cell_limit(
    tmp_path: Path, runtime, operation: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(
        source,
        runtime,
        script="lifecycle_limits.lua",
        tile_count=3,
        frames=3,
        unkeyed=1,
    )
    image = snapshot()
    image["rectangle"].update(width=1, height=1)
    image["rows"] = [[{"length": 1, "color": image["rows"][0][0]["color"]}]]
    parameters = {"image": image} if operation == "add" else {"tile_index": 1}
    code, result = run(
        "tileset",
        "tile",
        operation,
        **files(source, target),
        tile_key="new",
        **parameters,
    )
    assert code == 0, result
    assert result["affected_cels"] == []
