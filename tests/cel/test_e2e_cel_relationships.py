"""Native Cel placement, copy, link, and unlink through the public CLI."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from tests.cel.test_e2e_cel import _fixture, _run
from tests.layer.test_e2e_layer_mutation import _run as _run_layer
from tests.support import spa

pytestmark = pytest.mark.e2e


def test_set_copy_link_unlink_persist_native_relationships(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, "relationships.lua")
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    linked = {"layer": {"layer_path": [1]}, "frame_number": 4}
    copied = {"layer": {"layer_path": [2]}, "frame_number": 3}

    updated_file = tmp_path / "updated.aseprite"
    code, updated = _run(
        "set",
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
    assert code == 0, updated
    assert updated["cel"]["position"] == {"x": 2, "y": 1}
    assert updated["cel"]["opacity"] == 180
    assert updated["cel"]["z_index"] == -1
    assert updated["persisted_reopen_verified"] is True

    copied_file = tmp_path / "copied.aseprite"
    code, result = _run(
        "copy",
        {
            "source_sprite_file": str(updated_file),
            "target_sprite_file": str(copied_file),
            "in_place": False,
            "overwrite": False,
            "source": first,
            "destination": copied,
        },
    )
    assert code == 0, result
    assert result["cel"]["linked_cels"] == []
    assert result["cel"]["position"] == {"x": 2, "y": 1}
    assert result["cel"]["opacity"] == 180
    assert result["cel"]["z_index"] == -1
    assert result["cel"]["content"] == "nonempty"

    linked_file = tmp_path / "linked.aseprite"
    code, result = _run(
        "link",
        {
            "source_sprite_file": str(copied_file),
            "target_sprite_file": str(linked_file),
            "in_place": False,
            "overwrite": False,
            "source": first,
            "destination": linked,
        },
    )
    assert code == 0, result
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
    code, reopened = _run("get", {"sprite_file": str(linked_file), "target": first})
    assert code == 0, reopened
    assert reopened["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 4}]

    unlinked_file = tmp_path / "unlinked.aseprite"
    code, result = _run(
        "unlink",
        {
            "source_sprite_file": str(linked_file),
            "target_sprite_file": str(unlinked_file),
            "in_place": False,
            "overwrite": False,
            "target": linked,
        },
    )
    assert code == 0, result
    assert result["cel"]["linked_cels"] == []
    assert result["cel"]["content"] == "nonempty"
    code, reopened = _run("get", {"sprite_file": str(unlinked_file), "target": first})
    assert code == 0, reopened
    assert reopened["cel"]["linked_cels"] == []


def _paint(source: Path, target: Path) -> None:
    run = spa(
        "paint",
        "apply",
        "--input-json",
        json.dumps(
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
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert run.returncode == 0, run.stdout


def _render_pixel(source: Path, frame_number: int, output: Path) -> tuple[int, ...]:
    run = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(
            {
                "source_sprite_file": str(source),
                "destination": {"path": str(output), "if_exists": "fail"},
                "frame_number": frame_number,
                "export_image_area": {"kind": "canvas"},
                "layer_composition": {"mode": "visible"},
                "composition_color_mode": "preserve",
                "color_mode": "preserve",
                "color_profile": "preserve",
                "transparency": "preserve",
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    with Image.open(output) as image:
        return image.convert("RGBA").getpixel((1, 1))


def test_native_link_propagates_pixel_edit_and_unlink_stops_it(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    painted_link = tmp_path / "painted-link.aseprite"
    unlinked = tmp_path / "unlinked.aseprite"
    painted_unlink = tmp_path / "painted-unlink.aseprite"
    _fixture(source, "relationships.lua")
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    fourth = {"layer": {"layer_path": [1]}, "frame_number": 4}
    common = {"in_place": False, "overwrite": False}
    code, result = _run(
        "link",
        {
            **common,
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "source": first,
            "destination": fourth,
        },
    )
    assert code == 0, result
    _paint(linked, painted_link)
    assert (
        _render_pixel(painted_link, 1, tmp_path / "one.png")
        == _render_pixel(painted_link, 4, tmp_path / "four.png")
        == (255, 0, 0, 210)
    )
    code, result = _run(
        "unlink",
        {
            **common,
            "source_sprite_file": str(linked),
            "target_sprite_file": str(unlinked),
            "target": fourth,
        },
    )
    assert code == 0, result
    _paint(unlinked, painted_unlink)
    assert _render_pixel(painted_unlink, 1, tmp_path / "new-one.png") == (
        255,
        0,
        0,
        210,
    )
    assert _render_pixel(painted_unlink, 4, tmp_path / "new-four.png") == (
        30,
        40,
        50,
        210,
    )


def test_copy_remains_independent_after_source_paint(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    copied = tmp_path / "copied.aseprite"
    painted = tmp_path / "painted.aseprite"
    _fixture(source, "relationships.lua")
    code, result = _run(
        "copy",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(copied),
            "in_place": False,
            "overwrite": False,
            "source": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "destination": {"layer": {"layer_path": [2]}, "frame_number": 3},
        },
    )
    assert code == 0, result
    _paint(copied, painted)
    assert _render_pixel(painted, 1, tmp_path / "source.png") == (255, 0, 0, 210)
    assert _render_pixel(painted, 3, tmp_path / "copy.png") == (30, 40, 50, 210)


def test_copy_from_linked_source_reports_only_changed_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    copied = tmp_path / "copied.aseprite"
    _fixture(source, "relationships.lua")
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    fourth = {"layer": {"layer_path": [1]}, "frame_number": 4}
    destination = {"layer": {"layer_path": [2]}, "frame_number": 3}
    common = {"in_place": False, "overwrite": False}
    code, result = _run(
        "link",
        {
            **common,
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "source": first,
            "destination": fourth,
        },
    )
    assert code == 0, result
    code, result = _run(
        "copy",
        {
            **common,
            "source_sprite_file": str(linked),
            "target_sprite_file": str(copied),
            "source": first,
            "destination": destination,
        },
    )
    assert code == 0, result
    assert [cel["frame_number"] for cel in result["before_cels"]] == [1, 3, 4]
    assert [
        (cel["layer_path"], cel["frame_number"]) for cel in result["affected_cels"]
    ] == [([2], 3)]
    code, peer = _run("get", {"sprite_file": str(copied), "target": fourth})
    assert code == 0, peer
    assert peer["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 1}]


def test_set_reports_full_linked_scope_and_preserves_native_link(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    updated = tmp_path / "updated.aseprite"
    _fixture(source, "relationships.lua")
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    fourth = {"layer": {"layer_path": [1]}, "frame_number": 4}
    code, result = _run(
        "link",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "in_place": False,
            "overwrite": False,
            "source": first,
            "destination": fourth,
        },
    )
    assert code == 0, result
    code, result = _run(
        "set",
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
    assert code == 0, result
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1, 4]
    assert all(cel["position"] == {"x": 2, "y": 2} for cel in result["affected_cels"])
    assert all(cel["opacity"] == 120 for cel in result["affected_cels"])
    assert result["cel"]["z_index"] == 4
    assert result["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 4}]
    code, peer = _run("get", {"sprite_file": str(updated), "target": fourth})
    assert code == 0, peer
    assert peer["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 1}]
    assert peer["cel"]["opacity"] == 120
    assert peer["cel"]["z_index"] == 2

    reordered = tmp_path / "reordered.aseprite"
    code, result = _run(
        "set",
        {
            "source_sprite_file": str(updated),
            "target_sprite_file": str(reordered),
            "in_place": False,
            "overwrite": False,
            "target": first,
            "z_index": 6,
        },
    )
    assert code == 0, result
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1]
    code, peer = _run("get", {"sprite_file": str(reordered), "target": fourth})
    assert code == 0, peer
    assert peer["cel"]["z_index"] == 2


def test_link_to_earlier_absent_frame_preserves_timeline(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    copied = tmp_path / "copied.aseprite"
    linked = tmp_path / "linked.aseprite"
    _fixture(source, "relationships.lua")
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    fourth = {"layer": {"layer_path": [1]}, "frame_number": 4}
    second = {"layer": {"layer_path": [1]}, "frame_number": 2}
    common = {"in_place": False, "overwrite": False}
    code, result = _run(
        "copy",
        {
            **common,
            "source_sprite_file": str(source),
            "target_sprite_file": str(copied),
            "source": first,
            "destination": fourth,
        },
    )
    assert code == 0, result
    code, result = _run(
        "link",
        {
            **common,
            "source_sprite_file": str(copied),
            "target_sprite_file": str(linked),
            "source": fourth,
            "destination": second,
        },
    )
    assert code == 0, result
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
    tmp_path: Path,
    operation: str,
    primary: dict,
    destination: dict | None,
    code_expected: str,
) -> None:
    source = tmp_path / "source.aseprite"
    output = tmp_path / "output.aseprite"
    _fixture(source, "relationships.lua")
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
    code, result = _run(operation, request)
    assert code == 2, result
    assert result["code"] == code_expected
    assert not output.exists()


@pytest.mark.parametrize("invalid_role", ["source", "destination"])
def test_pair_layer_failure_identifies_address_role(
    tmp_path: Path, invalid_role: str
) -> None:
    source = tmp_path / "source.aseprite"
    output = tmp_path / "output.aseprite"
    _fixture(source, "relationships.lua")
    addresses = {
        "source": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "destination": {"layer": {"layer_path": [2]}, "frame_number": 3},
    }
    addresses[invalid_role] = {"layer": {"layer_path": [9]}, "frame_number": 1}
    code, result = _run(
        "copy",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(output),
            "in_place": False,
            "overwrite": False,
            **addresses,
        },
    )
    assert code == 2, result
    assert result["details"]["address_role"] == invalid_role
    assert result["details"]["address"]["layer_path"] == [9]
    assert not output.exists()


@pytest.mark.parametrize("locked_path", [[2], [2, 1]])
def test_unlink_refuses_locked_layer_hierarchy(
    tmp_path: Path, locked_path: list[int]
) -> None:
    source = tmp_path / "source.aseprite"
    linked = tmp_path / "linked.aseprite"
    locked = tmp_path / "locked.aseprite"
    output = tmp_path / "output.aseprite"
    _fixture(source, "relationships_group.lua")
    first = {"layer": {"layer_path": [2, 1]}, "frame_number": 1}
    second = {"layer": {"layer_path": [2, 1]}, "frame_number": 2}
    code, result = _run(
        "link",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked),
            "in_place": False,
            "overwrite": False,
            "source": first,
            "destination": second,
        },
    )
    assert code == 0, result
    code, result = _run_layer(
        "set",
        {
            "source_sprite_file": str(linked),
            "target_sprite_file": str(locked),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": locked_path},
            "properties": {"is_editable": False},
        },
    )
    assert code == 0, result
    code, result = _run(
        "unlink",
        {
            "source_sprite_file": str(locked),
            "target_sprite_file": str(output),
            "in_place": False,
            "overwrite": False,
            "target": second,
        },
    )
    assert code == 2, result
    assert result["code"] == "cel_unsupported_target"
    assert not output.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"position": {"x": 32768, "y": 0}},
        {"position": {"x": -32769, "y": 0}},
        {"position": {"x": 0, "y": 32768}},
        {"position": {"x": 0, "y": -32769}},
        {"z_index": 32768},
        {"z_index": -32769},
    ],
)
def test_set_rejects_unpersistable_cel_values(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    source = tmp_path / "source.aseprite"
    output = tmp_path / "output.aseprite"
    _fixture(source, "relationships.lua")
    code, result = _run(
        "set",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(output),
            "in_place": False,
            "overwrite": False,
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            **changes,
        },
    )
    assert code == 2, result
    assert result["code"] == "invalid_request"
    assert not output.exists()
