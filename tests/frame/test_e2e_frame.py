"""Frame operations against a real Aseprite Sprite."""

import struct
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, render_frame, run, run_lua
from tests.support import native_link_status, process_diagnostics

pytestmark = pytest.mark.e2e


FIXTURES = Path(__file__).parent / "fixtures"


def _tagged_sprite(runtime: RuntimeObservation, target: Path) -> None:
    """Write the tagged fixture Sprite to target."""
    lua = run_lua(FIXTURES / "tagged.lua", runtime, out=target)
    assert lua.returncode == 0, process_diagnostics(lua)


def _timeline_sprite(runtime: RuntimeObservation, target: Path) -> None:
    """Write the timeline fixture Sprite to target."""
    lua = run_lua(FIXTURES / "timeline.lua", runtime, out=target)
    assert lua.returncode == 0, process_diagnostics(lua)


def _add_second_slice_key(sprite_file: Path, frame_number: int = 3) -> None:
    """Create a later Slice Key in a fixture (Lua only edits Key 1)."""
    payload = bytearray(sprite_file.read_bytes())
    frame_offset = 128
    frame_size, magic, chunk_count = struct.unpack_from("<IHH", payload, frame_offset)
    assert magic == 0xF1FA
    chunk_offset = frame_offset + 16
    for _ in range(chunk_count):
        chunk_size, chunk_type = struct.unpack_from("<IH", payload, chunk_offset)
        if chunk_type == 0x2022:
            key_count, flags = struct.unpack_from("<II", payload, chunk_offset + 6)
            assert key_count == 1 and flags == 0
            second_key = struct.pack("<IiiII", frame_number - 1, 1, 0, 1, 1)
            payload[chunk_offset + chunk_size : chunk_offset + chunk_size] = second_key
            struct.pack_into("<I", payload, chunk_offset, chunk_size + len(second_key))
            struct.pack_into("<I", payload, chunk_offset + 6, 2)
            struct.pack_into("<I", payload, frame_offset, frame_size + len(second_key))
            struct.pack_into("<I", payload, 0, len(payload))
            sprite_file.write_bytes(payload)
            return
        chunk_offset += chunk_size
    raise AssertionError("fixture has no Slice chunk")


def test_set_changes_only_one_frame_duration_and_reports_observed_facts(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _timeline_sprite(runtime, source)
    before = expect_success(
        "sprite get",
        {
            "sprite_file": str(source),
            "inspection_scope": ["frames", "cels", "tags", "slices", "palettes"],
        },
    )
    changed = expect_success(
        "frame set",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 2,
            "duration_ms": 65535,
        },
    )
    assert changed["persisted_reopen_verified"] is True
    assert changed["before"]["frames"] == before["frames"]
    assert changed["sprite"]["frames"] == [
        {"frame_number": 1, "duration_ms": 120},
        {"frame_number": 2, "duration_ms": 65535},
        {"frame_number": 3, "duration_ms": 400},
        {"frame_number": 4, "duration_ms": 500},
    ]
    assert changed["frame_number_changes"] == []
    for section in ("cels", "tags", "slices", "palettes"):
        assert changed["before"][section] == changed["sprite"][section]
    assert (
        expect_success("frame list", {"sprite_file": str(target)})["frames"]
        == changed["sprite"]["frames"]
    )


@pytest.mark.parametrize(
    (
        "source_number",
        "target_number",
        "expected_durations",
        "expected_colors",
        "expected_changes",
    ),
    [
        (
            4,
            1,
            [500, 120, 300, 400],
            [120, 30, 60, 90],
            [(1, 2), (2, 3), (3, 4), (4, 1)],
        ),
        (1, 2, [300, 120, 400, 500], [60, 30, 90, 120], [(1, 2), (2, 1)]),
        (
            1,
            4,
            [300, 400, 500, 120],
            [60, 90, 120, 30],
            [(1, 4), (2, 1), (3, 2), (4, 3)],
        ),
    ],
)
def test_move_frame_preserves_timing_pixels_and_reports_native_references(
    runtime: RuntimeObservation,
    tmp_path: Path,
    source_number: int,
    target_number: int,
    expected_durations: list[int],
    expected_colors: list[int],
    expected_changes: list[tuple[int, int]],
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _timeline_sprite(runtime, source)
    before = expect_success(
        "sprite get",
        {
            "sprite_file": str(source),
            "inspection_scope": ["frames", "cels", "tags", "slices", "palettes"],
        },
    )
    moved = expect_success(
        "frame move",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": source_number,
            "target_frame_number": target_number,
        },
    )
    assert moved["cel_content_verified"] is True
    assert moved["persisted_reopen_verified"] is True
    assert moved["before"]["tags"] == before["tags"]
    assert moved["before"]["slices"] == before["slices"]
    assert [
        frame["duration_ms"] for frame in moved["sprite"]["frames"]
    ] == expected_durations
    assert moved["frame_number_changes"] == [
        {"before_frame_number": old, "after_frame_number": new}
        for old, new in expected_changes
    ]
    assert moved["sprite"]["tags"] != before["tags"]
    reopened = expect_success(
        "sprite get",
        {
            "sprite_file": str(target),
            "inspection_scope": ["frames", "cels", "tags", "slices", "palettes"],
        },
    )
    for section in ("frames", "cels", "tags", "slices", "palettes"):
        assert reopened[section] == moved["sprite"][section]
    for frame_number, color in enumerate(expected_colors, 1):
        rendered = render_frame(target, frame_number)
        assert rendered.getpixel((0, 0)) == (color, 0, 0, 255)


def test_remove_frame_shifts_retained_content_and_rejects_final_frame(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _timeline_sprite(runtime, source)
    removed = expect_success(
        "frame remove",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 2,
        },
    )
    assert removed["persisted_reopen_verified"] is True
    assert removed["cel_content_verified"] is True
    assert removed["frame_number_changes"] == [
        {"before_frame_number": 2, "after_frame_number": None},
        {"before_frame_number": 3, "after_frame_number": 2},
        {"before_frame_number": 4, "after_frame_number": 3},
    ]
    assert [frame["duration_ms"] for frame in removed["sprite"]["frames"]] == [
        120,
        400,
        500,
    ]
    assert [cel["frame_number"] for cel in removed["sprite"]["cels"]] == [1, 2, 3]
    assert removed["before"]["tags"] != removed["sprite"]["tags"]
    reopened = expect_success(
        "sprite get",
        {
            "sprite_file": str(target),
            "inspection_scope": ["frames", "cels", "tags", "slices", "palettes"],
        },
    )
    for section in ("frames", "cels", "tags", "slices", "palettes"):
        assert reopened[section] == removed["sprite"][section]

    one = tmp_path / "single.aseprite"
    final_target = tmp_path / "unpublished.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(one),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    failed = run(
        "frame remove",
        {
            "source_sprite_file": str(one),
            "target_sprite_file": str(final_target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 1,
        },
    )
    assert failed.returncode == 1, failed.envelope
    assert failed.envelope["code"] == "kernel_execution_failed"
    assert failed.envelope["details"]["reason"].endswith(
        ": cannot remove the final Frame"
    )
    assert not final_target.exists()
    assert expect_success("frame list", {"sprite_file": str(one)})["frames"] == [
        {"frame_number": 1, "duration_ms": 100}
    ]


def test_move_and_remove_report_reopened_slice_keys(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    moved_file = tmp_path / "moved.aseprite"
    removed_file = tmp_path / "removed.aseprite"
    _timeline_sprite(runtime, source)
    _add_second_slice_key(source)
    before = expect_success(
        "sprite get", {"sprite_file": str(source), "inspection_scope": ["slices"]}
    )
    assert [key["frame_number"] for key in before["slices"][0]["keys"]] == [1, 3]
    for operation, target_file, extra in (
        ("move", moved_file, {"source_frame_number": 4, "target_frame_number": 1}),
        ("remove", removed_file, {"frame_number": 3}),
    ):
        edited = expect_success(
            f"frame {operation}",
            {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target_file),
                "in_place": False,
                "overwrite": False,
                **extra,
            },
        )
        reopened = expect_success(
            "sprite get",
            {"sprite_file": str(target_file), "inspection_scope": ["slices"]},
        )
        assert edited["before"]["slices"] == before["slices"]
        assert edited["sprite"]["slices"] == reopened["slices"]
        assert edited["sprite"]["palettes"] is not None


def test_remove_reports_slice_key_dropped_by_native_save(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _timeline_sprite(runtime, source)
    _add_second_slice_key(source, frame_number=4)
    removed = expect_success(
        "frame remove",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 4,
        },
    )
    assert [key["frame_number"] for key in removed["before"]["slices"][0]["keys"]] == [
        1,
        4,
    ]
    assert [key["frame_number"] for key in removed["sprite"]["slices"][0]["keys"]] == [
        1
    ]
    assert (
        removed["sprite"]["slices"]
        == expect_success(
            "sprite get", {"sprite_file": str(target), "inspection_scope": ["slices"]}
        )["slices"]
    )


def test_move_same_frame_preserves_tag_and_does_not_report_renumbering(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _timeline_sprite(runtime, source)
    moved = expect_success(
        "frame move",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 2,
            "target_frame_number": 2,
        },
    )
    assert moved["frame_number_changes"] == []
    assert moved["before"]["tags"] == moved["sprite"]["tags"]
    assert moved["before"]["slices"] == moved["sprite"]["slices"]


def test_move_linked_cels_preserves_native_link(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    target = tmp_path / "moved.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    expect_success(
        "frame duplicate",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": "link",
        },
    )
    moved = expect_success(
        "frame move",
        {
            "source_sprite_file": str(linked),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "target_frame_number": 2,
        },
    )
    assert moved["cel_content_verified"] is True
    assert native_link_status(runtime, target, tmp_path / "link-status.json") is True


def test_move_background_cel_preserves_opaque_content(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    lua = run_lua(FIXTURES / "background_timeline.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    moved = expect_success(
        "frame move",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 3,
            "target_frame_number": 1,
        },
    )
    assert moved["cel_content_verified"] is True
    assert [cel["frame_number"] for cel in moved["sprite"]["cels"]] == [1, 2, 3]
    for frame_number, color in enumerate((90, 30, 60), 1):
        rendered = render_frame(target, frame_number)
        assert rendered.getpixel((0, 0)) == (color, 0, 0, 255)


@pytest.mark.parametrize(
    ("operation", "fields", "reason"),
    [
        (
            "set",
            {"frame_number": 5, "duration_ms": 100},
            ": Frame Number is outside the Sprite timeline",
        ),
        (
            "move",
            {"source_frame_number": 5, "target_frame_number": 1},
            ": Frame Number is outside the Sprite timeline",
        ),
        (
            "move",
            {"source_frame_number": 1, "target_frame_number": 5},
            ": target Frame Number is outside the Sprite timeline",
        ),
        (
            "remove",
            {"frame_number": 5},
            ": Frame Number is outside the Sprite timeline",
        ),
    ],
    ids=["set", "move-source", "move-target", "remove"],
)
def test_invalid_frame_edit_does_not_publish_target(
    runtime: RuntimeObservation,
    tmp_path: Path,
    operation: str,
    fields: dict[str, int],
    reason: str,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "unpublished.aseprite"
    _timeline_sprite(runtime, source)
    invocation = run(
        f"frame {operation}",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            **fields,
        },
    )
    assert invocation.returncode == 1, invocation.envelope
    assert invocation.envelope["code"] == "kernel_execution_failed"
    assert invocation.envelope["details"]["reason"].endswith(reason)
    assert not target.exists()
    assert [
        frame["duration_ms"]
        for frame in expect_success("frame list", {"sprite_file": str(source)})[
            "frames"
        ]
    ] == [120, 300, 400, 500]


def test_add_empty_frame_persists_one_based_position_and_duration(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    added = expect_success(
        "frame add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 1,
            "duration_ms": 340,
        },
    )
    assert added["inserted_frame"] == {"frame_number": 1, "duration_ms": 340}
    assert added["background_fill"] is None
    assert added["cel_relationships"] == []
    assert added["persisted_reopen_verified"] is True
    assert added["tag_adjustments"] == []
    assert added["sprite"]["frames"] == [
        {"frame_number": 1, "duration_ms": 340},
        {"frame_number": 2, "duration_ms": 100},
    ]
    assert [cel["frame_number"] for cel in added["sprite"]["cels"]] == [2]
    listed = expect_success("frame list", {"sprite_file": str(target)})
    assert listed["frames"] == added["sprite"]["frames"]
    got = expect_success("frame get", {"sprite_file": str(target), "frame_number": 1})
    assert got["frame"] == added["inserted_frame"]


@pytest.mark.parametrize("cel_mode", ["copy", "link"])
def test_duplicate_frame_uses_declared_cel_mode_and_persists(
    runtime: RuntimeObservation, tmp_path: Path, cel_mode: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / f"{cel_mode}.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    duplicated = expect_success(
        "frame duplicate",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": cel_mode,
            "duration_ms": 250,
        },
    )
    assert duplicated["inserted_frame"] == {"frame_number": 2, "duration_ms": 250}
    assert duplicated["source_cel_count"] == 1
    assert duplicated["inserted_cel_count"] == 1
    assert duplicated["cel_relationships_verified"] is True
    assert duplicated["background_fill"] is None
    assert duplicated["cel_relationships"] == [
        {"layer_path": [1], "source_frame_number": 1, "kind": cel_mode}
    ]
    assert duplicated["persisted_reopen_verified"] is True
    assert native_link_status(runtime, target, tmp_path / "links.json") is (
        cel_mode == "link"
    )
    assert expect_success("frame list", {"sprite_file": str(source)})["frames"] == [
        {"frame_number": 1, "duration_ms": 100}
    ]


def test_add_background_frame_uses_explicit_color(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    color = {"kind": "rgba", "red": 17, "green": 34, "blue": 51, "alpha": 255}
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {
                "kind": "background",
                "background_color": {
                    key: value for key, value in color.items() if key != "kind"
                },
            },
            "overwrite": False,
        },
    )
    added = expect_success(
        "frame add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 1,
            "duration_ms": 1,
            "background_color": color,
        },
    )
    assert added["inserted_cel_count"] == 1
    assert added["background_fill"] == color
    assert added["cel_relationships"] == []
    assert render_frame(target, 1).getpixel((0, 0)) == (17, 34, 51, 255)
    plan_target = tmp_path / "plan.aseprite"
    plan = expect_success(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(plan_target),
                "steps": [
                    {
                        "operation": "sprite get",
                        "input": {"inspection_scope": ["cels"]},
                    },
                    {
                        "operation": "frame add",
                        "input": {
                            "frame_number": 2,
                            "duration_ms": 100,
                            "background_color": color,
                        },
                    },
                ],
            }
        },
    )
    assert plan["steps"][0]["result"]["sprite"]["metadata"]["cel_count"] == 1
    assert plan["steps"][1]["result"]["background_fill"] == color
    assert plan["steps"][1]["result"]["inserted_cel_count"] == 1
    assert plan["final_sprite"]["metadata"]["cel_count"] == 2


def test_add_reports_native_tag_range_adjustment(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "tagged.aseprite"
    target = tmp_path / "target.aseprite"
    _tagged_sprite(runtime, source)
    added = expect_success(
        "frame add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 2,
            "duration_ms": 65535,
        },
    )
    assert added["inserted_frame"] == {"frame_number": 2, "duration_ms": 65535}
    assert added["tag_adjustments"] == [
        {
            "tag_number": 1,
            "name": "walk",
            "before_from_frame": 1,
            "before_to_frame": 2,
            "after_from_frame": 1,
            "after_to_frame": 3,
        }
    ]
    assert added["sprite"]["tags"][0]["to_frame"] == 3


def test_plan_frame_steps_match_standalone_semantics(tmp_path: Path) -> None:
    target = tmp_path / "plan.aseprite"
    result = expect_success(
        "plan run",
        {
            "plan": {
                "target_sprite_file": str(target),
                "steps": [
                    {
                        "operation": "sprite create",
                        "input": {
                            "width": 3,
                            "height": 2,
                            "color_mode": "rgb",
                            "initial_layer": {"kind": "transparent"},
                        },
                    },
                    {
                        "operation": "frame add",
                        "input": {"frame_number": 2, "duration_ms": 340},
                    },
                    {"operation": "frame list", "input": {}},
                    {
                        "operation": "frame duplicate",
                        "input": {"source_frame_number": 1, "cel_mode": "link"},
                    },
                    {"operation": "frame get", "input": {"frame_number": 2}},
                ],
                "postconditions": {"frame_count": 3},
            }
        },
    )
    assert result["persisted_reopen_verified"] is True
    assert result["steps"][1]["result"]["inserted_frame"] == {
        "frame_number": 2,
        "duration_ms": 340,
    }
    assert len(result["steps"][2]["result"]["frames"]) == 2
    assert result["steps"][3]["result"]["inserted_frame"] == {
        "frame_number": 2,
        "duration_ms": 100,
    }
    assert result["steps"][3]["result"]["cel_relationships"] == [
        {"layer_path": [1], "source_frame_number": 1, "kind": "link"}
    ]
    assert result["steps"][4]["result"]["frame"]["duration_ms"] == 100
    assert expect_success("frame list", {"sprite_file": str(target)})["frames"] == [
        {"frame_number": 1, "duration_ms": 100},
        {"frame_number": 2, "duration_ms": 100},
        {"frame_number": 3, "duration_ms": 340},
    ]


def test_missing_frame_get_has_standalone_and_plan_failure_parity(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "unpublished.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    standalone = run("frame get", {"sprite_file": str(source), "frame_number": 2})
    plan = run(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "steps": [
                    {"operation": "frame get", "input": {"frame_number": 2}},
                    {
                        "operation": "frame add",
                        "input": {"frame_number": 2, "duration_ms": 100},
                    },
                ],
            }
        },
    )
    assert standalone.returncode != 0
    assert plan.returncode != 0
    standalone_failure = standalone.envelope
    plan_failure = plan.envelope
    assert standalone_failure["code"] == plan_failure["code"] == "invalid_request"
    assert standalone_failure["details"]["errors"][0]["code"] == "frame_not_found"
    assert plan_failure["details"]["errors"] == [
        {
            "location": ["plan", "steps", 0, "input", "frame_number"],
            "code": "frame_not_found",
            "message": "Frame Number is outside the Sprite timeline",
        }
    ]
    assert not target.exists()


def test_invalid_add_never_publishes_target(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _tagged_sprite(runtime, source)
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "frame_number": 4,
        "duration_ms": 100,
    }
    result = run("frame add", request)
    assert result.returncode == 1, result.envelope
    assert result.envelope["code"] == "kernel_execution_failed"
    assert result.envelope["details"]["reason"].endswith(
        ": Frame insertion position is out of range"
    )
    assert not target.exists()
    assert expect_success("frame list", {"sprite_file": str(source)})["frames"] == [
        {"frame_number": 1, "duration_ms": 120},
        {"frame_number": 2, "duration_ms": 340},
    ]


def test_duplicate_preserves_absent_cels(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _tagged_sprite(runtime, source)
    duplicated = expect_success(
        "frame duplicate",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 2,
            "cel_mode": "link",
        },
    )
    assert duplicated["inserted_frame"] == {"frame_number": 3, "duration_ms": 340}
    assert duplicated["source_cel_count"] == 0
    assert duplicated["inserted_cel_count"] == 0
    assert all(cel["frame_number"] != 3 for cel in duplicated["sprite"]["cels"])


@pytest.mark.parametrize("cel_mode", ["copy", "link"])
def test_duplicate_background_cel_preserves_declared_mode(
    runtime: RuntimeObservation, tmp_path: Path, cel_mode: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {
                "kind": "background",
                "background_color": {"red": 17, "green": 34, "blue": 51, "alpha": 255},
            },
            "overwrite": False,
        },
    )
    duplicated = expect_success(
        "frame duplicate",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": cel_mode,
        },
    )
    assert duplicated["source_cel_count"] == 1
    assert duplicated["inserted_cel_count"] == 1
    assert native_link_status(runtime, target, tmp_path / "links.json") is (
        cel_mode == "link"
    )


@pytest.mark.parametrize(
    ("mode", "color"),
    [
        ("grayscale", {"kind": "grayscale", "gray": 60, "alpha": 255}),
        ("indexed", {"kind": "palette-index", "index": 1}),
    ],
)
def test_add_background_frame_accepts_color_compatible_with_sprite_mode(
    runtime: RuntimeObservation, tmp_path: Path, mode: str, color: dict[str, object]
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    lua = run_lua(FIXTURES / "background_modes.lua", runtime, mode=mode, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    added = expect_success(
        "frame add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 2,
            "duration_ms": 100,
            "background_color": color,
        },
    )
    assert added["inserted_cel_count"] == 1
    assert added["background_fill"] == color
    assert added["sprite"]["metadata"]["color_mode"] == mode


@pytest.mark.parametrize("index", [0, 200])
def test_indexed_background_rejects_transparent_or_absent_palette_color(
    runtime: RuntimeObservation, tmp_path: Path, index: int
) -> None:
    source = tmp_path / "indexed.aseprite"
    target = tmp_path / "target.aseprite"
    lua = run_lua(
        FIXTURES / "background_modes.lua", runtime, mode="indexed", out=source
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "frame_number": 2,
        "duration_ms": 100,
        "background_color": {"kind": "palette-index", "index": index},
    }
    result = run("frame add", request)
    assert result.returncode != 0
    failure = result.envelope
    assert failure["code"] == "kernel_execution_failed"
    assert "Background Palette" in failure["details"]["reason"]
    assert not target.exists()


def test_copy_mode_overrides_continuous_layer_policy(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "continuous.aseprite"
    target = tmp_path / "copy.aseprite"
    lua = run_lua(FIXTURES / "continuous.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    duplicated = expect_success(
        "frame duplicate",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": "copy",
        },
    )
    assert duplicated["sprite"]["layers"][0]["is_continuous"] is True
    assert native_link_status(runtime, target, tmp_path / "links.json") is False


def test_in_place_add_commits_to_the_source_entry(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    _tagged_sprite(runtime, source)
    added = expect_success(
        "frame add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(source),
            "in_place": True,
            "overwrite": True,
            "frame_number": 3,
            "duration_ms": 200,
        },
    )
    assert added["target_commit"]["target_sprite_file"] == str(source)
    assert expect_success("frame list", {"sprite_file": str(source)})["frames"] == [
        {"frame_number": 1, "duration_ms": 120},
        {"frame_number": 2, "duration_ms": 340},
        {"frame_number": 3, "duration_ms": 200},
    ]


@pytest.mark.parametrize("cel_mode", ["copy", "link"])
def test_duplicate_uses_one_inserted_frame_for_multiple_source_cels(
    runtime: RuntimeObservation, tmp_path: Path, cel_mode: str
) -> None:
    source = tmp_path / "multi.aseprite"
    target = tmp_path / "target.aseprite"
    lua = run_lua(FIXTURES / "multi_cel.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    duplicated = expect_success(
        "frame duplicate",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": cel_mode,
        },
    )
    assert duplicated["sprite"]["metadata"]["frame_count"] == 2
    assert duplicated["source_cel_count"] == 2
    assert duplicated["inserted_cel_count"] == 2
    assert {tuple(item["layer_path"]) for item in duplicated["cel_relationships"]} == {
        (1,),
        (2,),
    }
    assert {item["kind"] for item in duplicated["cel_relationships"]} == {cel_mode}


def test_frame_mutations_preserve_verified_layer_uuids(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "uuid-source.aseprite"
    standalone_target = tmp_path / "standalone.aseprite"
    plan_target = tmp_path / "plan.aseprite"
    lua = run_lua(FIXTURES / "multi_cel.lua", runtime, out=source, uuids=True)
    assert lua.returncode == 0, process_diagnostics(lua)
    source_layers = expect_success(
        "sprite get", {"sprite_file": str(source), "inspection_scope": ["layers"]}
    )["layers"]
    assert all(layer["layer_uuid"] is not None for layer in source_layers)
    standalone = expect_success(
        "frame duplicate",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(standalone_target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": "copy",
        },
    )
    assert standalone["sprite"]["layers"] == source_layers
    plan = expect_success(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(plan_target),
                "steps": [
                    {
                        "operation": "frame duplicate",
                        "input": {"source_frame_number": 1, "cel_mode": "link"},
                    }
                ],
            }
        },
    )
    assert plan["final_sprite"]["layers"] == source_layers
