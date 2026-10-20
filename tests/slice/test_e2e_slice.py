"""Slice snapshot reads and bounded mutations through the installed public CLI."""

import re

import pytest

from tests.native_invocation import expect_success, run, run_lua
from tests.slice.support import FIXTURES, fixture, mutation
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


def test_complete_slice_reads_report_ordered_keys_and_exact_coverage(tmp_path, runtime):
    source = tmp_path / "source.aseprite"
    fixture(runtime, source)
    original = source.read_bytes()
    listed = expect_success("slice list", {"sprite_file": str(source)})
    assert listed["frame_count"] == 6
    assert listed["coordinate_space"] == "canvas-pixel"
    assert [item["slice_index"] for item in listed["slices"]] == [1, 2, 3, 4]
    multi = next(item for item in listed["slices"] if item["name"] == "multi")
    assert [key["frame_number"] for key in multi["keys"]] == [1, 3, 5]
    assert [key["effective_frame_range"] for key in multi["keys"]] == [
        {"from_frame": 1, "to_frame": 2},
        {"from_frame": 3, "to_frame": 4},
        {"from_frame": 5, "to_frame": 6},
    ]
    assert multi["keys"][0]["bounds"] == {"x": -2, "y": 3, "width": 6, "height": 4}
    assert multi["keys"][0]["center"] == {"x": 1, "y": 1, "width": 2, "height": 2}
    assert multi["keys"][0]["pivot"] == {"x": -1, "y": 5}
    late = next(item for item in listed["slices"] if item["name"] == "late")
    assert [key["effective_frame_range"] for key in late["keys"]] == [
        {"from_frame": 3, "to_frame": 6}
    ]
    got = expect_success(
        "slice get", {"sprite_file": str(source), "target": {"slice_name": "multi"}}
    )
    assert got["slice"] == multi, got
    got = expect_success(
        "slice get",
        {"sprite_file": str(source), "target": {"slice_index": multi["slice_index"]}},
    )
    assert got["slice"] == multi, got
    outcome = run(
        "slice get", {"sprite_file": str(source), "target": {"slice_name": "same"}}
    )
    failure = outcome.envelope
    assert outcome.returncode != 0 and failure["code"] == "slice_ambiguous", failure
    assert source.read_bytes() == original


def test_set_static_geometry_and_metadata_survives_reopen(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "edited.aseprite"
    fixture(runtime, source)
    before = expect_success("slice list", {"sprite_file": str(source)})
    selected = next(item for item in before["slices"] if item["data"] == "first")
    changed = expect_success(
        "slice set",
        {
            **mutation(source, target),
            "target": {"slice_index": selected["slice_index"]},
            "properties": {
                "name": "",
                "data": "",
                "bounds": {"x": 3, "y": -4, "width": 5, "height": 7},
                "center": None,
                "pivot": {"x": 2, "y": -3},
            },
        },
    )
    assert changed["previous_slice"] == selected
    reopened = expect_success(
        "slice get", {"sprite_file": str(target), "target": {"slice_name": ""}}
    )
    edited = reopened["slice"]
    assert edited in changed["slices"]
    assert edited["data"] == "" and edited["color"] == selected["color"]
    assert edited["keys"] == [
        {
            "frame_number": 1,
            "effective_frame_range": {"from_frame": 1, "to_frame": 6},
            "bounds": {"x": 3, "y": -4, "width": 5, "height": 7},
            "center": None,
            "pivot": {"x": 2, "y": -3},
        }
    ]
    lua = run_lua(FIXTURES / "preserved.lua", runtime, source=target)
    assert lua.returncode == 0, process_diagnostics(lua)


def test_add_returns_reopened_addresses_and_preserves_existing_slice_keys(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "added.aseprite"
    fixture(runtime, source)
    original = source.read_bytes()
    before = expect_success("slice list", {"sprite_file": str(source)})
    added = expect_success(
        "slice add",
        {
            **mutation(source, target),
            "name": "panel",
            "data": "interactive",
            "color": {"red": 12, "green": 34, "blue": 56, "alpha": 78},
            "bounds": {"x": -3, "y": 2, "width": 8, "height": 6},
            "center": {"x": 1, "y": 2, "width": 3, "height": 2},
            "pivot": {"x": -1, "y": 7},
        },
    )
    assert added["persisted_reopen_verified"] is True
    reopened = expect_success("slice list", {"sprite_file": str(target)})
    assert added["slices"] == reopened["slices"]
    panel = next(item for item in added["slices"] if item["name"] == "panel")
    assert panel["data"] == "interactive"
    assert panel["color"] == {"red": 12, "green": 34, "blue": 56, "alpha": 78}
    assert panel["keys"] == [
        {
            "frame_number": 1,
            "effective_frame_range": {"from_frame": 1, "to_frame": 6},
            "bounds": {"x": -3, "y": 2, "width": 8, "height": 6},
            "center": {"x": 1, "y": 2, "width": 3, "height": 2},
            "pivot": {"x": -1, "y": 7},
        }
    ]
    for old in before["slices"]:
        assert {key: value for key, value in old.items() if key != "slice_index"} in [
            {key: value for key, value in item.items() if key != "slice_index"}
            for item in added["slices"]
        ]
    assert source.read_bytes() == original


def test_remove_exact_duplicate_and_reread_current_indexes(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "removed.aseprite"
    fixture(runtime, source)
    original = source.read_bytes()
    before = expect_success("slice list", {"sprite_file": str(source)})
    selected = next(item for item in before["slices"] if item["data"] == "second")
    removed = expect_success(
        "slice remove",
        {
            **mutation(source, target),
            "target": {"slice_index": selected["slice_index"]},
        },
    )
    assert removed["previous_slice"] == selected
    assert len(removed["slices"]) == 3
    assert [item["data"] for item in removed["slices"] if item["name"] == "same"] == [
        "first"
    ]
    reopened = expect_success("slice list", {"sprite_file": str(target)})
    assert removed["slices"] == reopened["slices"]
    assert source.read_bytes() == original


@pytest.mark.parametrize("name", ["multi", "late"])
def test_metadata_edits_preserve_all_keys_and_remove_whole_animated_slice(
    tmp_path, runtime, name
):
    source, target = tmp_path / "source.aseprite", tmp_path / "edited.aseprite"
    fixture(runtime, source)
    before = expect_success(
        "slice get", {"sprite_file": str(source), "target": {"slice_name": name}}
    )
    edited = expect_success(
        "slice set",
        {
            **mutation(source, target),
            "target": {"slice_name": name},
            "properties": {
                "name": "renamed",
                "data": "complete keys",
                "color": {"red": 10, "green": 20, "blue": 30, "alpha": 0},
            },
        },
    )
    fact = next(item for item in edited["slices"] if item["name"] == "renamed")
    assert fact["keys"] == before["slice"]["keys"]
    assert fact["data"] == "complete keys"
    assert fact["color"] == {"red": 0, "green": 0, "blue": 0, "alpha": 0}
    removed = expect_success(
        "slice remove",
        {
            "source_sprite_file": str(target),
            "target_sprite_file": str(target),
            "in_place": True,
            "overwrite": True,
            "target": {"slice_name": "renamed"},
        },
    )
    assert len(removed["slices"]) == 3
    assert not any(item["name"] == "renamed" for item in removed["slices"])
    lua = run_lua(FIXTURES / "preserved.lua", runtime, source=target)
    assert lua.returncode == 0, process_diagnostics(lua)


@pytest.mark.parametrize("name", ["multi", "late"])
@pytest.mark.parametrize(
    "properties",
    [
        {"bounds": {"x": 0, "y": 0, "width": 1, "height": 1}},
        {"center": None},
        {"pivot": {"x": 1, "y": 2}},
    ],
)
def test_nonstatic_geometry_rejected_without_publishing(
    tmp_path, runtime, name, properties
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(runtime, source)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    request = mutation(
        source, target, target={"slice_name": name}, properties=properties
    )
    request["overwrite"] = True
    outcome = run("slice set", request)
    failure = outcome.envelope
    assert (
        outcome.returncode == 2 and failure["code"] == "slice_geometry_unsupported"
    ), failure
    assert source.read_bytes() == original
    assert target.read_bytes() == b"existing target"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "source.aseprite",
        "target.aseprite",
    ]


@pytest.mark.parametrize("operation", ["get", "set", "remove"])
def test_names_and_indexes_resolve_exactly_before_mutation(
    tmp_path, runtime, operation
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(runtime, source)
    original = source.read_bytes()
    request = (
        {"sprite_file": str(source)} if operation == "get" else mutation(source, target)
    )
    if operation == "set":
        request["properties"] = {"name": "changed"}
    for address, expected in [
        ({"slice_name": "same"}, "slice_ambiguous"),
        ({"slice_name": "missing"}, "slice_missing"),
        ({"slice_index": 99}, "slice_missing"),
    ]:
        outcome = run(f"slice {operation}", {**request, "target": address})
        failure = outcome.envelope
        assert outcome.returncode == 2 and failure["code"] == expected, failure
    assert source.read_bytes() == original and not target.exists()


def test_remove_last_slice_returns_empty_current_snapshot(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(runtime, source, animated=False)
    removed = expect_success(
        "slice remove", {**mutation(source, target), "target": {"slice_index": 1}}
    )
    assert len(removed["slices"]) == 1, removed
    empty = expect_success(
        "slice remove",
        {
            "source_sprite_file": str(target),
            "target_sprite_file": str(target),
            "in_place": True,
            "overwrite": True,
            "target": {"slice_index": 1},
        },
    )
    assert empty["slices"] == [], empty
    listed = expect_success("slice list", {"sprite_file": str(target)})
    assert listed["slices"] == [], listed


def test_native_malformed_user_data_cannot_publish_target(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(runtime, source)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    request = mutation(
        source,
        target,
        target={"slice_name": "multi"},
        properties={"data": "line\nbreak"},
    )
    request["overwrite"] = True
    outcome = run("slice set", request)
    failure = outcome.envelope
    assert outcome.returncode != 0 and failure["code"] == "kernel_execution_failed", (
        failure
    )
    # Measured with Aseprite 1.3.18.5: the native export writes the line feed
    # unescaped, so the Slice reader cannot decode the exported vendor data.
    assert re.fullmatch(
        r".*slice_inspect\.lua:\d+: unescaped \(10\) in string",
        failure["details"]["reason"],
    ), failure
    assert source.read_bytes() == original and target.read_bytes() == b"existing target"
