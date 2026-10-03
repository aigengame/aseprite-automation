"""Slice snapshot reads and bounded mutations through the installed public CLI."""

import pytest

from tests.slice.support import fixture, mutation, native_script, run

pytestmark = pytest.mark.e2e


def test_complete_slice_reads_report_ordered_keys_and_exact_coverage(tmp_path):
    source = tmp_path / "source.aseprite"
    fixture(source)
    original = source.read_bytes()
    code, listed = run("slice", "list", sprite_file=str(source))
    assert code == 0, listed
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
    code, got = run(
        "slice", "get", sprite_file=str(source), target={"slice_name": "multi"}
    )
    assert code == 0 and got["slice"] == multi, got
    code, got = run(
        "slice",
        "get",
        sprite_file=str(source),
        target={"slice_index": multi["slice_index"]},
    )
    assert code == 0 and got["slice"] == multi, got
    code, failure = run(
        "slice", "get", sprite_file=str(source), target={"slice_name": "same"}
    )
    assert code != 0 and failure["code"] == "slice_ambiguous", failure
    assert source.read_bytes() == original


def test_set_static_geometry_and_metadata_survives_reopen(tmp_path):
    source, target = tmp_path / "source.aseprite", tmp_path / "edited.aseprite"
    fixture(source)
    _, before = run("slice", "list", sprite_file=str(source))
    selected = next(item for item in before["slices"] if item["data"] == "first")
    code, changed = run(
        "slice",
        "set",
        **mutation(source, target),
        target={"slice_index": selected["slice_index"]},
        properties={
            "name": "",
            "data": "",
            "bounds": {"x": 3, "y": -4, "width": 5, "height": 7},
            "center": None,
            "pivot": {"x": 2, "y": -3},
        },
    )
    assert code == 0, changed
    assert changed["previous_slice"] == selected
    code, reopened = run(
        "slice", "get", sprite_file=str(target), target={"slice_name": ""}
    )
    assert code == 0, reopened
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
    native_script("preserved.lua", source=target)


def test_add_returns_reopened_addresses_and_preserves_existing_slice_keys(tmp_path):
    source, target = tmp_path / "source.aseprite", tmp_path / "added.aseprite"
    fixture(source)
    original = source.read_bytes()
    _, before = run("slice", "list", sprite_file=str(source))
    code, added = run(
        "slice",
        "add",
        **mutation(source, target),
        name="panel",
        data="interactive",
        color={"red": 12, "green": 34, "blue": 56, "alpha": 78},
        bounds={"x": -3, "y": 2, "width": 8, "height": 6},
        center={"x": 1, "y": 2, "width": 3, "height": 2},
        pivot={"x": -1, "y": 7},
    )
    assert code == 0, added
    assert added["persisted_reopen_verified"] is True
    code, reopened = run("slice", "list", sprite_file=str(target))
    assert code == 0 and added["slices"] == reopened["slices"]
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


def test_remove_exact_duplicate_and_reread_current_indexes(tmp_path):
    source, target = tmp_path / "source.aseprite", tmp_path / "removed.aseprite"
    fixture(source)
    original = source.read_bytes()
    _, before = run("slice", "list", sprite_file=str(source))
    selected = next(item for item in before["slices"] if item["data"] == "second")
    code, removed = run(
        "slice",
        "remove",
        **mutation(source, target),
        target={"slice_index": selected["slice_index"]},
    )
    assert code == 0, removed
    assert removed["previous_slice"] == selected
    assert len(removed["slices"]) == 3
    assert [item["data"] for item in removed["slices"] if item["name"] == "same"] == [
        "first"
    ]
    _, reopened = run("slice", "list", sprite_file=str(target))
    assert removed["slices"] == reopened["slices"]
    assert source.read_bytes() == original


@pytest.mark.parametrize("name", ["multi", "late"])
def test_metadata_edits_preserve_all_keys_and_remove_whole_animated_slice(
    tmp_path, name
):
    source, target = tmp_path / "source.aseprite", tmp_path / "edited.aseprite"
    fixture(source)
    _, before = run(
        "slice", "get", sprite_file=str(source), target={"slice_name": name}
    )
    code, edited = run(
        "slice",
        "set",
        **mutation(source, target),
        target={"slice_name": name},
        properties={
            "name": "renamed",
            "data": "complete keys",
            "color": {"red": 10, "green": 20, "blue": 30, "alpha": 0},
        },
    )
    assert code == 0, edited
    fact = next(item for item in edited["slices"] if item["name"] == "renamed")
    assert fact["keys"] == before["slice"]["keys"]
    assert fact["data"] == "complete keys"
    assert fact["color"] == {"red": 0, "green": 0, "blue": 0, "alpha": 0}
    code, removed = run(
        "slice",
        "remove",
        source_sprite_file=str(target),
        target_sprite_file=str(target),
        in_place=True,
        overwrite=True,
        target={"slice_name": "renamed"},
    )
    assert code == 0, removed
    assert len(removed["slices"]) == 3
    assert not any(item["name"] == "renamed" for item in removed["slices"])
    native_script("preserved.lua", source=target)


@pytest.mark.parametrize("name", ["multi", "late"])
@pytest.mark.parametrize(
    "properties",
    [
        {"bounds": {"x": 0, "y": 0, "width": 1, "height": 1}},
        {"center": None},
        {"pivot": {"x": 1, "y": 2}},
    ],
)
def test_nonstatic_geometry_rejected_without_publishing(tmp_path, name, properties):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    request = mutation(
        source, target, target={"slice_name": name}, properties=properties
    )
    request["overwrite"] = True
    code, failure = run("slice", "set", **request)
    assert code == 2 and failure["code"] == "slice_geometry_unsupported", failure
    assert source.read_bytes() == original
    assert target.read_bytes() == b"existing target"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "source.aseprite",
        "target.aseprite",
    ]


@pytest.mark.parametrize("operation", ["get", "set", "remove"])
def test_names_and_indexes_resolve_exactly_before_mutation(tmp_path, operation):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source)
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
        code, failure = run("slice", operation, **request, target=address)
        assert code == 2 and failure["code"] == expected, failure
    assert source.read_bytes() == original and not target.exists()


def test_remove_last_slice_returns_empty_current_snapshot(tmp_path):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, animated=False)
    code, removed = run(
        "slice", "remove", **mutation(source, target), target={"slice_index": 1}
    )
    assert code == 0 and len(removed["slices"]) == 1, removed
    code, empty = run(
        "slice",
        "remove",
        source_sprite_file=str(target),
        target_sprite_file=str(target),
        in_place=True,
        overwrite=True,
        target={"slice_index": 1},
    )
    assert code == 0 and empty["slices"] == [], empty
    code, listed = run("slice", "list", sprite_file=str(target))
    assert code == 0 and listed["slices"] == [], listed


def test_native_malformed_user_data_cannot_publish_target(tmp_path):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    request = mutation(
        source,
        target,
        target={"slice_name": "multi"},
        properties={"data": "line\nbreak"},
    )
    request["overwrite"] = True
    code, failure = run("slice", "set", **request)
    assert code != 0 and failure["code"] == "kernel_execution_failed", failure
    assert source.read_bytes() == original and target.read_bytes() == b"existing target"
