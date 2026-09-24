"""Frame operations against a real Aseprite Sprite."""

import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _run(*command: str, request: dict[str, object]) -> dict[str, object]:
    payload = {**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}
    result = spa(*command, "--input-json", json.dumps(payload))
    assert result.returncode == 0, result.stdout
    return json.loads(result.stdout)


def _run_fixture(name: str, **params: str) -> None:
    binary = Path(os.environ["SPA_TEST_ASEPRITE"])
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    fixture = Path(__file__).parent / "fixtures" / name
    with tempfile.TemporaryDirectory(prefix="spa-frame-fixture-") as work:
        prepared = prepare_invocation(binary, resource, Path(work))
        arguments = [
            item
            for key, value in params.items()
            for item in ("--script-param", f"{key}={value}")
        ]
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                *arguments,
                "--script",
                str(fixture),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr


def _tagged_sprite(target: Path) -> None:
    _run_fixture("tagged.lua", out=str(target))


def _timeline_sprite(target: Path) -> None:
    _run_fixture("timeline.lua", out=str(target))


def _add_second_slice_key(sprite_file: Path) -> None:
    """Create an Aseprite file with a Frame 3 Slice Key (Lua only edits Key 1)."""
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
            second_key = struct.pack("<IiiII", 2, 1, 0, 1, 1)
            payload[chunk_offset + chunk_size : chunk_offset + chunk_size] = second_key
            struct.pack_into("<I", payload, chunk_offset, chunk_size + len(second_key))
            struct.pack_into("<I", payload, chunk_offset + 6, 2)
            struct.pack_into("<I", payload, frame_offset, frame_size + len(second_key))
            struct.pack_into("<I", payload, 0, len(payload))
            sprite_file.write_bytes(payload)
            return
        chunk_offset += chunk_size
    raise AssertionError("fixture has no Slice chunk")


def _native_link_status(target: Path, out: Path) -> bool:
    _run_fixture("inspect_links.lua", source=str(target), out=str(out))
    return json.loads(out.read_text(encoding="utf-8"))["linked"]


def test_set_changes_only_one_frame_duration_and_reports_observed_facts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _timeline_sprite(source)
    before = _run(
        "sprite",
        "get",
        request={
            "sprite_file": str(source),
            "inspection_scope": ["frames", "cels", "tags", "slices", "palettes"],
        },
    )
    changed = _run(
        "frame",
        "set",
        request={
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
        _run("frame", "list", request={"sprite_file": str(target)})["frames"]
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
    tmp_path: Path,
    source_number: int,
    target_number: int,
    expected_durations: list[int],
    expected_colors: list[int],
    expected_changes: list[tuple[int, int]],
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _timeline_sprite(source)
    before = _run(
        "sprite",
        "get",
        request={
            "sprite_file": str(source),
            "inspection_scope": ["frames", "cels", "tags", "slices", "palettes"],
        },
    )
    moved = _run(
        "frame",
        "move",
        request={
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
    reopened = _run(
        "sprite",
        "get",
        request={
            "sprite_file": str(target),
            "inspection_scope": ["frames", "cels", "tags", "slices", "palettes"],
        },
    )
    for section in ("frames", "cels", "tags", "slices", "palettes"):
        assert reopened[section] == moved["sprite"][section]
    for frame_number, color in enumerate(expected_colors, 1):
        png = tmp_path / f"frame-{frame_number}.png"
        _run(
            "export",
            "image",
            request={
                "source_sprite_file": str(target),
                "destination": {"path": str(png), "if_exists": "fail"},
                "frame_number": frame_number,
                "color_mode": "preserve",
                "color_profile": "preserve",
                "transparency": "preserve",
            },
        )
        with Image.open(png) as image:
            assert image.convert("RGBA").getpixel((0, 0)) == (color, 0, 0, 255)


def test_remove_frame_shifts_retained_content_and_rejects_final_frame(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _timeline_sprite(source)
    removed = _run(
        "frame",
        "remove",
        request={
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
    reopened = _run(
        "sprite",
        "get",
        request={
            "sprite_file": str(target),
            "inspection_scope": ["frames", "cels", "tags", "slices", "palettes"],
        },
    )
    for section in ("frames", "cels", "tags", "slices", "palettes"):
        assert reopened[section] == removed["sprite"][section]

    one = tmp_path / "single.aseprite"
    final_target = tmp_path / "unpublished.aseprite"
    _run(
        "sprite",
        "create",
        request={
            "target_sprite_file": str(one),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    failed = spa(
        "frame",
        "remove",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(one),
                "target_sprite_file": str(final_target),
                "in_place": False,
                "overwrite": False,
                "frame_number": 1,
            }
        ),
    )
    assert failed.returncode != 0
    assert not final_target.exists()
    assert _run("frame", "list", request={"sprite_file": str(one)})["frames"] == [
        {"frame_number": 1, "duration_ms": 100}
    ]


def test_move_and_remove_report_reopened_slice_keys(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    moved_file = tmp_path / "moved.aseprite"
    removed_file = tmp_path / "removed.aseprite"
    _timeline_sprite(source)
    _add_second_slice_key(source)
    before = _run(
        "sprite",
        "get",
        request={"sprite_file": str(source), "inspection_scope": ["slices"]},
    )
    assert [key["frame_number"] for key in before["slices"][0]["keys"]] == [1, 3]
    for operation, target_file, extra in (
        ("move", moved_file, {"source_frame_number": 4, "target_frame_number": 1}),
        ("remove", removed_file, {"frame_number": 3}),
    ):
        edited = _run(
            "frame",
            operation,
            request={
                "source_sprite_file": str(source),
                "target_sprite_file": str(target_file),
                "in_place": False,
                "overwrite": False,
                **extra,
            },
        )
        reopened = _run(
            "sprite",
            "get",
            request={"sprite_file": str(target_file), "inspection_scope": ["slices"]},
        )
        assert edited["before"]["slices"] == before["slices"]
        assert edited["sprite"]["slices"] == reopened["slices"]
        assert edited["sprite"]["palettes"] is not None


def test_move_same_frame_preserves_tag_and_does_not_report_renumbering(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _timeline_sprite(source)
    moved = _run(
        "frame",
        "move",
        request={
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


def test_move_linked_cels_preserves_native_link(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    target = tmp_path / "moved.aseprite"
    _run(
        "sprite",
        "create",
        request={
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    _run(
        "frame",
        "duplicate",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": "link",
        },
    )
    moved = _run(
        "frame",
        "move",
        request={
            "source_sprite_file": str(linked),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "target_frame_number": 2,
        },
    )
    assert moved["cel_content_verified"] is True
    assert _native_link_status(target, tmp_path / "link-status.json") is True


def test_move_background_cel_preserves_opaque_content(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _run_fixture("background_timeline.lua", out=str(source))
    moved = _run(
        "frame",
        "move",
        request={
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
        png = tmp_path / f"background-{frame_number}.png"
        _run(
            "export",
            "image",
            request={
                "source_sprite_file": str(target),
                "destination": {"path": str(png), "if_exists": "fail"},
                "frame_number": frame_number,
                "color_mode": "preserve",
                "color_profile": "preserve",
                "transparency": "preserve",
            },
        )
        with Image.open(png) as image:
            assert image.convert("RGBA").getpixel((0, 0)) == (color, 0, 0, 255)


@pytest.mark.parametrize(
    ("operation", "fields"),
    [
        ("set", {"frame_number": 5, "duration_ms": 100}),
        ("set", {"frame_number": 1, "duration_ms": 0}),
        ("move", {"source_frame_number": 5, "target_frame_number": 1}),
        ("move", {"source_frame_number": 1, "target_frame_number": 5}),
        ("remove", {"frame_number": 5}),
    ],
)
def test_invalid_frame_edit_does_not_publish_target(
    tmp_path: Path, operation: str, fields: dict[str, int]
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "unpublished.aseprite"
    _timeline_sprite(source)
    invocation = spa(
        "frame",
        operation,
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": False,
                "overwrite": False,
                **fields,
            }
        ),
    )
    assert invocation.returncode != 0
    assert not target.exists()
    assert [
        frame["duration_ms"]
        for frame in _run("frame", "list", request={"sprite_file": str(source)})[
            "frames"
        ]
    ] == [120, 300, 400, 500]


def test_add_empty_frame_persists_one_based_position_and_duration(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _run(
        "sprite",
        "create",
        request={
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    added = _run(
        "frame",
        "add",
        request={
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
    listed = _run("frame", "list", request={"sprite_file": str(target)})
    assert listed["frames"] == added["sprite"]["frames"]
    got = _run("frame", "get", request={"sprite_file": str(target), "frame_number": 1})
    assert got["frame"] == added["inserted_frame"]


@pytest.mark.parametrize("cel_mode", ["copy", "link"])
def test_duplicate_frame_uses_declared_cel_mode_and_persists(
    tmp_path: Path, cel_mode: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / f"{cel_mode}.aseprite"
    _run(
        "sprite",
        "create",
        request={
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    duplicated = _run(
        "frame",
        "duplicate",
        request={
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
    assert _native_link_status(target, tmp_path / "links.json") is (cel_mode == "link")
    assert _run("frame", "list", request={"sprite_file": str(source)})["frames"] == [
        {"frame_number": 1, "duration_ms": 100}
    ]


def test_add_background_frame_uses_explicit_color(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    png = tmp_path / "frame.png"
    color = {"kind": "rgba", "red": 17, "green": 34, "blue": 51, "alpha": 255}
    _run(
        "sprite",
        "create",
        request={
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
    added = _run(
        "frame",
        "add",
        request={
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
    _run(
        "export",
        "image",
        request={
            "source_sprite_file": str(target),
            "destination": {"path": str(png), "if_exists": "fail"},
            "frame_number": 1,
            "color_mode": "preserve",
            "color_profile": "preserve",
            "transparency": "preserve",
        },
    )
    with Image.open(png) as image:
        assert image.convert("RGBA").getpixel((0, 0)) == (17, 34, 51, 255)
    plan_target = tmp_path / "plan.aseprite"
    plan = _run(
        "plan",
        "run",
        request={
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(plan_target),
                "steps": [
                    {
                        "operation": "frame add",
                        "input": {
                            "frame_number": 2,
                            "duration_ms": 100,
                            "background_color": color,
                        },
                    }
                ],
            }
        },
    )
    assert plan["steps"][0]["result"]["background_fill"] == color


def test_add_reports_native_tag_range_adjustment(tmp_path: Path) -> None:
    source = tmp_path / "tagged.aseprite"
    target = tmp_path / "target.aseprite"
    _tagged_sprite(source)
    added = _run(
        "frame",
        "add",
        request={
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
    result = _run(
        "plan",
        "run",
        request={
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
    assert _run("frame", "list", request={"sprite_file": str(target)})["frames"] == [
        {"frame_number": 1, "duration_ms": 100},
        {"frame_number": 2, "duration_ms": 100},
        {"frame_number": 3, "duration_ms": 340},
    ]


def test_missing_frame_get_has_standalone_and_plan_failure_parity(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "unpublished.aseprite"
    _run(
        "sprite",
        "create",
        request={
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    standalone = spa(
        "frame",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(source),
                "frame_number": 2,
            }
        ),
    )
    plan = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
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
                },
            }
        ),
    )
    assert standalone.returncode != 0
    assert plan.returncode != 0
    standalone_failure = json.loads(standalone.stdout)
    plan_failure = json.loads(plan.stdout)
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("frame_number", 0),
        ("frame_number", 4),
        ("duration_ms", 0),
        ("duration_ms", 65536),
    ],
)
def test_invalid_add_never_publishes_target(
    tmp_path: Path, field: str, value: int
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _tagged_sprite(source)
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "frame_number": 2,
        "duration_ms": 100,
    }
    request[field] = value
    result = spa(
        "frame",
        "add",
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert result.returncode != 0
    assert not target.exists()
    assert _run("frame", "list", request={"sprite_file": str(source)})["frames"] == [
        {"frame_number": 1, "duration_ms": 120},
        {"frame_number": 2, "duration_ms": 340},
    ]


def test_duplicate_preserves_absent_cels(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _tagged_sprite(source)
    duplicated = _run(
        "frame",
        "duplicate",
        request={
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
    tmp_path: Path, cel_mode: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _run(
        "sprite",
        "create",
        request={
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
    duplicated = _run(
        "frame",
        "duplicate",
        request={
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
    assert _native_link_status(target, tmp_path / "links.json") is (cel_mode == "link")


@pytest.mark.parametrize(
    ("mode", "color"),
    [
        ("grayscale", {"kind": "grayscale", "gray": 60, "alpha": 255}),
        ("indexed", {"kind": "palette-index", "index": 1}),
    ],
)
def test_add_background_frame_accepts_color_compatible_with_sprite_mode(
    tmp_path: Path, mode: str, color: dict[str, object]
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _run_fixture("background_modes.lua", mode=mode, out=str(source))
    added = _run(
        "frame",
        "add",
        request={
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
    tmp_path: Path, index: int
) -> None:
    source = tmp_path / "indexed.aseprite"
    target = tmp_path / "target.aseprite"
    _run_fixture("background_modes.lua", mode="indexed", out=str(source))
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "frame_number": 2,
        "duration_ms": 100,
        "background_color": {"kind": "palette-index", "index": index},
    }
    result = spa("frame", "add", "--input-json", json.dumps(request))
    assert result.returncode != 0
    failure = json.loads(result.stdout)
    assert failure["code"] == "kernel_execution_failed"
    assert "Background Palette" in failure["details"]["reason"]
    assert not target.exists()


def test_copy_mode_overrides_continuous_layer_policy(tmp_path: Path) -> None:
    source = tmp_path / "continuous.aseprite"
    target = tmp_path / "copy.aseprite"
    _run_fixture("continuous.lua", out=str(source))
    duplicated = _run(
        "frame",
        "duplicate",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": "copy",
        },
    )
    assert duplicated["sprite"]["layers"][0]["is_continuous"] is True
    assert _native_link_status(target, tmp_path / "links.json") is False


def test_in_place_add_commits_to_the_source_entry(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    _tagged_sprite(source)
    added = _run(
        "frame",
        "add",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(source),
            "in_place": True,
            "overwrite": True,
            "frame_number": 3,
            "duration_ms": 200,
        },
    )
    assert added["target_commit"]["target_sprite_file"] == str(source)
    assert _run("frame", "list", request={"sprite_file": str(source)})["frames"] == [
        {"frame_number": 1, "duration_ms": 120},
        {"frame_number": 2, "duration_ms": 340},
        {"frame_number": 3, "duration_ms": 200},
    ]


@pytest.mark.parametrize("cel_mode", ["copy", "link"])
def test_duplicate_uses_one_inserted_frame_for_multiple_source_cels(
    tmp_path: Path, cel_mode: str
) -> None:
    source = tmp_path / "multi.aseprite"
    target = tmp_path / "target.aseprite"
    _run_fixture("multi_cel.lua", out=str(source))
    duplicated = _run(
        "frame",
        "duplicate",
        request={
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


def test_frame_mutations_preserve_verified_layer_uuids(tmp_path: Path) -> None:
    source = tmp_path / "uuid-source.aseprite"
    standalone_target = tmp_path / "standalone.aseprite"
    plan_target = tmp_path / "plan.aseprite"
    _run_fixture("multi_cel.lua", out=str(source), uuids="true")
    source_layers = _run(
        "sprite",
        "get",
        request={"sprite_file": str(source), "inspection_scope": ["layers"]},
    )["layers"]
    assert all(layer["layer_uuid"] is not None for layer in source_layers)
    standalone = _run(
        "frame",
        "duplicate",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(standalone_target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": "copy",
        },
    )
    assert standalone["sprite"]["layers"] == source_layers
    plan = _run(
        "plan",
        "run",
        request={
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
