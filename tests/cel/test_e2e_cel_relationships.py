"""Native Cel placement, copy, link, and unlink through the public CLI."""

from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, render_frame, run, run_lua
from tests.support import cel_relationships_sprite, process_diagnostics

pytestmark = pytest.mark.e2e


def test_set_copy_link_unlink_persist_native_relationships(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    cel_relationships_sprite(runtime, source)
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    linked = {"layer": {"layer_path": [1]}, "frame_number": 4}
    copied = {"layer": {"layer_path": [2]}, "frame_number": 3}

    updated_file = tmp_path / "updated.aseprite"
    updated = expect_success(
        "cel set",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(updated_file),
            "in_place": False,
            "overwrite": False,
            "target": first,
            "position": {"x": 2, "y": 1},
            "opacity": 180,
            "z_index": -1,
        },
    )
    assert updated["cel"]["position"] == {"x": 2, "y": 1}
    assert updated["cel"]["opacity"] == 180
    assert updated["cel"]["z_index"] == -1
    assert updated["persisted_reopen_verified"] is True

    copied_file = tmp_path / "copied.aseprite"
    result = expect_success(
        "cel copy",
        {
            "source_sprite_file": str(updated_file),
            "target_sprite_file": str(copied_file),
            "in_place": False,
            "overwrite": False,
            "source": first,
            "destination": copied,
        },
    )
    assert result["cel"]["linked_cels"] == []
    assert result["cel"]["position"] == {"x": 2, "y": 1}
    assert result["cel"]["opacity"] == 180
    assert result["cel"]["z_index"] == -1
    assert result["cel"]["content"] == "nonempty"

    linked_file = tmp_path / "linked.aseprite"
    result = expect_success(
        "cel link",
        {
            "source_sprite_file": str(copied_file),
            "target_sprite_file": str(linked_file),
            "in_place": False,
            "overwrite": False,
            "source": first,
            "destination": linked,
        },
    )
    assert result["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 1}]
    assert result["cel"]["position"] == {"x": 2, "y": 1}
    assert result["persisted_reopen_verified"] is True
    assert [frame["duration_ms"] for frame in result["sprite"]["frames"]] == [
        100,
        200,
        300,
        400,
    ]
    assert [
        (tag["from_frame"], tag["to_frame"]) for tag in result["sprite"]["tags"]
    ] == [(2, 3)]
    reopened = expect_success(
        "cel get", {"sprite_file": str(linked_file), "target": first}
    )
    assert reopened["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 4}]

    unlinked_file = tmp_path / "unlinked.aseprite"
    result = expect_success(
        "cel unlink",
        {
            "source_sprite_file": str(linked_file),
            "target_sprite_file": str(unlinked_file),
            "in_place": False,
            "overwrite": False,
            "target": linked,
        },
    )
    assert result["cel"]["linked_cels"] == []
    assert result["cel"]["content"] == "nonempty"
    reopened = expect_success(
        "cel get", {"sprite_file": str(unlinked_file), "target": first}
    )
    assert reopened["cel"]["linked_cels"] == []


def _paint(source: Path, target: Path) -> None:
    """Paint pixel (0, 0) of the Cel at [1]@1 red, from source into target."""
    expect_success(
        "paint apply",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1], "frame_number": 1},
            "patch": {
                "coordinate_space": "image-pixel",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                "runs": [
                    {
                        "x": 0,
                        "y": 0,
                        "length": 1,
                        "color": {
                            "kind": "rgba",
                            "red": 255,
                            "green": 0,
                            "blue": 0,
                            "alpha": 255,
                        },
                    }
                ],
            },
        },
    )


def test_native_link_propagates_pixel_edit_and_unlink_stops_it(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    painted_link = tmp_path / "painted-link.aseprite"
    unlinked = tmp_path / "unlinked.aseprite"
    painted_unlink = tmp_path / "painted-unlink.aseprite"
    cel_relationships_sprite(runtime, source)
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    fourth = {"layer": {"layer_path": [1]}, "frame_number": 4}
    common = {"in_place": False, "overwrite": False}
    expect_success(
        "cel link",
        {
            **common,
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "source": first,
            "destination": fourth,
        },
    )
    _paint(linked, painted_link)
    assert (
        render_frame(painted_link, 1).getpixel((1, 1))
        == render_frame(painted_link, 4).getpixel((1, 1))
        == (255, 0, 0, 210)
    )
    expect_success(
        "cel unlink",
        {
            **common,
            "source_sprite_file": str(linked),
            "target_sprite_file": str(unlinked),
            "target": fourth,
        },
    )
    _paint(unlinked, painted_unlink)
    assert render_frame(painted_unlink, 1).getpixel((1, 1)) == (
        255,
        0,
        0,
        210,
    )
    assert render_frame(painted_unlink, 4).getpixel((1, 1)) == (
        30,
        40,
        50,
        210,
    )


def test_copy_remains_independent_after_source_paint(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    copied = tmp_path / "copied.aseprite"
    painted = tmp_path / "painted.aseprite"
    cel_relationships_sprite(runtime, source)
    expect_success(
        "cel copy",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(copied),
            "in_place": False,
            "overwrite": False,
            "source": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "destination": {"layer": {"layer_path": [2]}, "frame_number": 3},
        },
    )
    _paint(copied, painted)
    assert render_frame(painted, 1).getpixel((1, 1)) == (255, 0, 0, 210)
    assert render_frame(painted, 3).getpixel((1, 1)) == (30, 40, 50, 210)


def test_copy_from_linked_source_reports_only_changed_destination(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    copied = tmp_path / "copied.aseprite"
    cel_relationships_sprite(runtime, source)
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    fourth = {"layer": {"layer_path": [1]}, "frame_number": 4}
    destination = {"layer": {"layer_path": [2]}, "frame_number": 3}
    common = {"in_place": False, "overwrite": False}
    result = expect_success(
        "cel link",
        {
            **common,
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "source": first,
            "destination": fourth,
        },
    )
    result = expect_success(
        "cel copy",
        {
            **common,
            "source_sprite_file": str(linked),
            "target_sprite_file": str(copied),
            "source": first,
            "destination": destination,
        },
    )
    assert [cel["frame_number"] for cel in result["before_cels"]] == [1, 3, 4]
    assert [
        (cel["layer_path"], cel["frame_number"]) for cel in result["affected_cels"]
    ] == [([2], 3)]
    peer = expect_success("cel get", {"sprite_file": str(copied), "target": fourth})
    assert peer["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 1}]


def test_set_reports_full_linked_scope_and_preserves_native_link(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    updated = tmp_path / "updated.aseprite"
    cel_relationships_sprite(runtime, source)
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    fourth = {"layer": {"layer_path": [1]}, "frame_number": 4}
    result = expect_success(
        "cel link",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "in_place": False,
            "overwrite": False,
            "source": first,
            "destination": fourth,
        },
    )
    result = expect_success(
        "cel set",
        {
            "source_sprite_file": str(linked),
            "target_sprite_file": str(updated),
            "in_place": False,
            "overwrite": False,
            "target": first,
            "position": {"x": 2, "y": 2},
            "opacity": 120,
            "z_index": 4,
        },
    )
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1, 4]
    assert all(cel["position"] == {"x": 2, "y": 2} for cel in result["affected_cels"])
    assert all(cel["opacity"] == 120 for cel in result["affected_cels"])
    assert result["cel"]["z_index"] == 4
    assert result["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 4}]
    peer = expect_success("cel get", {"sprite_file": str(updated), "target": fourth})
    assert peer["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 1}]
    assert peer["cel"]["opacity"] == 120
    assert peer["cel"]["z_index"] == 2

    reordered = tmp_path / "reordered.aseprite"
    result = expect_success(
        "cel set",
        {
            "source_sprite_file": str(updated),
            "target_sprite_file": str(reordered),
            "in_place": False,
            "overwrite": False,
            "target": first,
            "z_index": 6,
        },
    )
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1]
    peer = expect_success("cel get", {"sprite_file": str(reordered), "target": fourth})
    assert peer["cel"]["z_index"] == 2


def test_link_to_earlier_absent_frame_preserves_timeline(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    copied = tmp_path / "copied.aseprite"
    linked = tmp_path / "linked.aseprite"
    cel_relationships_sprite(runtime, source)
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    fourth = {"layer": {"layer_path": [1]}, "frame_number": 4}
    second = {"layer": {"layer_path": [1]}, "frame_number": 2}
    common = {"in_place": False, "overwrite": False}
    result = expect_success(
        "cel copy",
        {
            **common,
            "source_sprite_file": str(source),
            "target_sprite_file": str(copied),
            "source": first,
            "destination": fourth,
        },
    )
    result = expect_success(
        "cel link",
        {
            **common,
            "source_sprite_file": str(copied),
            "target_sprite_file": str(linked),
            "source": fourth,
            "destination": second,
        },
    )
    assert result["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 4}]
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [2, 4]
    assert [frame["duration_ms"] for frame in result["sprite"]["frames"]] == [
        100,
        200,
        300,
        400,
    ]
    assert [
        (tag["from_frame"], tag["to_frame"]) for tag in result["sprite"]["tags"]
    ] == [(2, 3)]


@pytest.mark.parametrize(
    ("operation", "primary", "destination", "code_expected"),
    [
        (
            "copy",
            {"layer": {"layer_path": [1]}, "frame_number": 2},
            {"layer": {"layer_path": [2]}, "frame_number": 3},
            "cel_not_found",
        ),
        (
            "link",
            {"layer": {"layer_path": [1]}, "frame_number": 1},
            {"layer": {"layer_path": [2]}, "frame_number": 3},
            "cel_unsupported_target",
        ),
        (
            "copy",
            {"layer": {"layer_path": [1]}, "frame_number": 1},
            {"layer": {"layer_path": [1]}, "frame_number": 1},
            "cel_already_exists",
        ),
        (
            "unlink",
            {"layer": {"layer_path": [1]}, "frame_number": 1},
            None,
            "cel_unsupported_target",
        ),
        (
            "set",
            {"layer": {"layer_path": [1]}, "frame_number": 2},
            None,
            "cel_not_found",
        ),
    ],
)
def test_refusal_keeps_target_absent(
    runtime: RuntimeObservation,
    tmp_path: Path,
    operation: str,
    primary: dict,
    destination: dict | None,
    code_expected: str,
) -> None:
    source = tmp_path / "source.aseprite"
    output = tmp_path / "output.aseprite"
    cel_relationships_sprite(runtime, source)
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(output),
        "in_place": False,
        "overwrite": False,
    }
    if destination is None:
        request["target"] = primary
        if operation == "set":
            request["opacity"] = 100
    else:
        request["source"] = primary
        request["destination"] = destination
    outcome = run(f"cel {operation}", request)
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == code_expected
    assert not output.exists()


@pytest.mark.parametrize("invalid_role", ["source", "destination"])
def test_pair_layer_failure_identifies_address_role(
    runtime: RuntimeObservation, tmp_path: Path, invalid_role: str
) -> None:
    source = tmp_path / "source.aseprite"
    output = tmp_path / "output.aseprite"
    cel_relationships_sprite(runtime, source)
    addresses = {
        "source": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "destination": {"layer": {"layer_path": [2]}, "frame_number": 3},
    }
    addresses[invalid_role] = {"layer": {"layer_path": [9]}, "frame_number": 1}
    outcome = run(
        "cel copy",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(output),
            "in_place": False,
            "overwrite": False,
            **addresses,
        },
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["details"]["address_role"] == invalid_role
    assert result["details"]["address"]["layer_path"] == [9]
    assert not output.exists()


@pytest.mark.parametrize("locked_path", [[2], [2, 1]])
def test_unlink_refuses_locked_layer_hierarchy(
    runtime: RuntimeObservation, tmp_path: Path, locked_path: list[int]
) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    locked = tmp_path / "locked.aseprite"
    output = tmp_path / "output.aseprite"
    lua = run_lua(
        Path(__file__).parent / "fixtures" / "relationships_group.lua",
        runtime,
        out=source,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    first = {"layer": {"layer_path": [2, 1]}, "frame_number": 1}
    second = {"layer": {"layer_path": [2, 1]}, "frame_number": 2}
    result = expect_success(
        "cel link",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "in_place": False,
            "overwrite": False,
            "source": first,
            "destination": second,
        },
    )
    result = expect_success(
        "layer set",
        {
            "source_sprite_file": str(linked),
            "target_sprite_file": str(locked),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": locked_path},
            "properties": {"is_editable": False},
        },
    )
    outcome = run(
        "cel unlink",
        {
            "source_sprite_file": str(locked),
            "target_sprite_file": str(output),
            "in_place": False,
            "overwrite": False,
            "target": second,
        },
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "cel_unsupported_target"
    assert not output.exists()
