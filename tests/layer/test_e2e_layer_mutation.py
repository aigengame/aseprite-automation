"""Layer mutations through the installed CLI and real Aseprite."""

import json
from importlib.resources import files
from pathlib import Path

import pytest

from spa.authoring.document.sprite import SPRITE_INSPECTION_RESOURCES
from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run, run_lua
from tests.support import native_link_status, process_diagnostics

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"


def _mutations_sprite(runtime: RuntimeObservation, target: Path) -> None:
    """Write the regular, group and nested Layer Sprite of `mutations.lua` to target."""
    lua = run_lua(FIXTURES / "mutations.lua", runtime, out=target)
    assert lua.returncode == 0, process_diagnostics(lua)


def _mutation_request(source: Path, target: Path) -> dict[str, object]:
    """Return the file fields of a Layer mutation from source to a new target."""
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
    }


def test_set_layer_properties_and_report_rendered_change(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _mutations_sprite(runtime, source)
    result = expect_success(
        "layer set",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [2]},
            "properties": {
                "name": "renamed",
                "is_visible": False,
                "is_editable": False,
                "opacity": 128,
                "blend_mode": "multiply",
            },
        },
    )
    assert result["persisted_reopen_verified"] is True
    assert result["before"]["layers"][1]["name"] == "upper"
    changed = result["after"]["layers"][1]
    assert changed["name"] == "renamed"
    assert changed["is_visible"] is False
    assert changed["is_editable"] is False
    assert changed["opacity"] == 128
    assert changed["blend_mode"] == "multiply"
    assert [2] in result["affected_before"]["layer_paths"]
    assert [2] in result["affected_after"]["layer_paths"]
    assert len(result["rendered_frames"]) == 2
    assert all(
        frame["before_digest"] != frame["after_digest"]
        for frame in result["rendered_frames"]
    )
    assert target.is_file()


def test_move_reorders_one_sibling_and_reports_shifted_addresses(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "moved.aseprite"
    _mutations_sprite(runtime, source)
    result = expect_success(
        "layer move",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [2]},
            "stack_index": 1,
        },
    )
    assert [layer["name"] for layer in result["before"]["layers"]] == [
        "lower",
        "upper",
        "group",
    ]
    assert [layer["name"] for layer in result["after"]["layers"]] == [
        "upper",
        "lower",
        "group",
    ]
    assert {tuple(path) for path in result["affected_before"]["layer_paths"]} >= {
        (1,),
        (2,),
    }
    assert {tuple(path) for path in result["affected_after"]["layer_paths"]} >= {
        (1,),
        (2,),
    }
    assert result["persisted_reopen_verified"] is True


def test_remove_group_reports_complete_deleted_subtree_and_cels(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "removed.aseprite"
    _mutations_sprite(runtime, source)
    result = expect_success(
        "layer remove",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [3]},
        },
    )
    assert result["after"]["metadata"]["layer_count"] == 2
    assert [3] in result["affected_before"]["layer_paths"]
    assert [3, 1] in result["affected_before"]["layer_paths"]
    assert {"layer_path": [3, 1], "frame_number": 1} in result["affected_before"][
        "cels"
    ]
    assert result["affected_after"]["layer_paths"] == []
    assert (
        result["rendered_frames"][0]["before_digest"]
        != result["rendered_frames"][0]["after_digest"]
    )


def test_merge_down_preserves_lower_identity_and_persisted_pixels(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "merged.aseprite"
    _mutations_sprite(runtime, source)
    result = expect_success(
        "layer merge",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [2]},
        },
    )
    assert result["after"]["metadata"]["layer_count"] == 3
    assert [layer["name"] for layer in result["after"]["layers"]] == [
        "lower",
        "group",
    ]
    assert [1] in result["affected_before"]["layer_paths"]
    assert [2] in result["affected_before"]["layer_paths"]
    assert [1] in result["affected_after"]["layer_paths"]
    assert result["persisted_reopen_verified"] is True


@pytest.mark.parametrize(
    ("command", "details", "expected_code"),
    [
        (
            "set",
            {"target": {"layer_path": [3]}, "properties": {"opacity": 12}},
            "layer_unsupported_target",
        ),
        (
            "move",
            {"target": {"layer_path": [2]}, "stack_index": 5},
            "layer_invalid_position",
        ),
        ("merge", {"target": {"layer_path": [3]}}, "layer_unsupported_target"),
        ("merge", {"target": {"layer_path": [1]}}, "layer_unsupported_target"),
    ],
)
def test_rejected_layer_mutation_leaves_no_target(
    runtime: RuntimeObservation,
    tmp_path: Path,
    command: str,
    details: dict,
    expected_code: str,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "rejected.aseprite"
    _mutations_sprite(runtime, source)
    outcome = run(f"layer {command}", {**_mutation_request(source, target), **details})
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == expected_code
    assert not target.exists()


def test_remove_rejects_group_containing_tilemap(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "tilemap.aseprite"
    target = tmp_path / "rejected.aseprite"
    lua = run_lua(FIXTURES / "tilemap_subtree.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    outcome = run(
        "layer remove",
        {**_mutation_request(source, target), "target": {"layer_path": [2]}},
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert not target.exists()


@pytest.mark.parametrize(
    ("command", "extra"),
    [
        ("set", {"properties": {"is_visible": False}}),
        ("move", {"stack_index": 2}),
        ("merge", {}),
    ],
)
def test_background_is_not_an_eligible_mutation_target(
    runtime: RuntimeObservation, tmp_path: Path, command: str, extra: dict
) -> None:
    source = tmp_path / "unsupported.aseprite"
    target = tmp_path / "rejected.aseprite"
    lua = run_lua(FIXTURES / "tilemap_subtree.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    outcome = run(
        f"layer {command}",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [1]},
            **extra,
        },
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert not target.exists()


def test_merge_compositing_ignores_both_ambient_preference_values(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "merge_composite.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    kernel = files("spa.kernel")
    reports = []
    for ambient in (False, True):
        target = tmp_path / f"merged-{ambient}.aseprite"
        report = tmp_path / f"merged-{ambient}.json"
        workspace = tmp_path / f"workspace-{ambient}"
        workspace.mkdir()
        lua = run_lua(
            FIXTURES / "merge_under_ambient.lua",
            runtime,
            ambient=ambient,
            source=source,
            target=target,
            report=report,
            **{
                resource.parameter_name: kernel.joinpath(resource.package_path)
                for resource in SPRITE_INSPECTION_RESOURCES
            },
            cel=kernel.joinpath("document/cel/cel_support.lua"),
            mutation=kernel.joinpath("document/layer/layer_mutation_support.lua"),
            effective_palette=kernel.joinpath("color/effective_palette.lua"),
            digest=kernel.joinpath("foundation/digest.lua"),
            persistence=kernel.joinpath("document/sprite/sprite_persistence.lua"),
            workspace=workspace,
        )
        assert lua.returncode == 0, process_diagnostics(lua)
        reports.append(json.loads(report.read_text()))
    assert (
        reports[0]
        == reports[1]
        == {
            "layer_count": 1,
            "lower_name": "lower",
            "ambient_restored": True,
            "first_pixel": [75, 64, 14, 195],
            "after_digest": reports[0]["after_digest"],
        }
    )


def test_nested_move_stays_within_group_and_merge_targets_adjacent_sibling(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "nested.aseprite"
    moved = tmp_path / "moved.aseprite"
    merged = tmp_path / "merged.aseprite"
    lua = run_lua(FIXTURES / "nested_mutations.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    move = expect_success(
        "layer move",
        {
            **_mutation_request(source, moved),
            "target": {"layer_path": [2, 2]},
            "stack_index": 1,
        },
    )
    assert [layer["name"] for layer in move["after"]["layers"][1]["children"]] == [
        "nested-upper",
        "nested-lower",
    ]
    assert [2, 1] in move["affected_after"]["layer_paths"]
    assert [2, 2] in move["affected_after"]["layer_paths"]

    merge = expect_success(
        "layer merge",
        {
            **_mutation_request(source, merged),
            "target": {"layer_path": [2, 2]},
        },
    )
    assert [layer["name"] for layer in merge["after"]["layers"][1]["children"]] == [
        "nested-lower"
    ]
    assert merge["after"]["metadata"]["layer_count"] == 3
    assert [2, 1] in merge["affected_after"]["layer_paths"]


def test_set_group_properties_without_image_only_fields(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "nested.aseprite"
    target = tmp_path / "group-set.aseprite"
    lua = run_lua(FIXTURES / "nested_mutations.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "layer set",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [2]},
            "properties": {
                "name": "renamed-group",
                "is_visible": False,
                "is_editable": False,
            },
        },
    )
    group = result["after"]["layers"][1]
    assert group["name"] == "renamed-group"
    assert group["is_visible"] is False
    assert group["is_editable"] is False
    assert {tuple(path) for path in result["affected_after"]["layer_paths"]} >= {
        (2,),
        (2, 1),
        (2, 2),
    }


@pytest.mark.parametrize(
    ("path", "name"),
    [([2], "renamed-image"), ([3], "renamed-group")],
)
def test_rename_reports_only_the_changed_layer(
    runtime: RuntimeObservation, tmp_path: Path, path: list[int], name: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "renamed.aseprite"
    _mutations_sprite(runtime, source)
    result = expect_success(
        "layer set",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": path},
            "properties": {"name": name},
        },
    )
    assert result["affected_before"]["layer_paths"] == [path]
    assert result["affected_after"]["layer_paths"] == [path]
    assert result["affected_before"]["cels"] == []
    assert result["affected_after"]["cels"] == []
    assert all(
        frame["before_digest"] == frame["after_digest"]
        for frame in result["rendered_frames"]
    )


@pytest.mark.parametrize(
    ("command", "extra"),
    [("set", {"properties": {"name": "upper"}}), ("move", {"stack_index": 2})],
)
def test_noop_reports_no_changed_objects(
    runtime: RuntimeObservation, tmp_path: Path, command: str, extra: dict
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "noop.aseprite"
    _mutations_sprite(runtime, source)
    result = expect_success(
        f"layer {command}",
        {**_mutation_request(source, target), "target": {"layer_path": [2]}, **extra},
    )
    for phase in ("affected_before", "affected_after"):
        assert result[phase] == {"layer_paths": [], "cels": []}
    assert all(
        frame["before_digest"] == frame["after_digest"]
        for frame in result["rendered_frames"]
    )


def test_move_rejects_crossing_background_before_publishing(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "rejected.aseprite"
    lua = run_lua(FIXTURES / "tilemap_subtree.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    outcome = run(
        "layer move",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [2]},
            "stack_index": 1,
        },
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "layer_invalid_position"
    assert not target.exists()


@pytest.mark.parametrize("field", ["is_visible", "is_editable"])
def test_group_flag_change_omits_descendants_already_effectively_disabled(
    runtime: RuntimeObservation, tmp_path: Path, field: str
) -> None:
    source = tmp_path / "source.aseprite"
    child_disabled = tmp_path / "child-disabled.aseprite"
    group_disabled = tmp_path / "group-disabled.aseprite"
    _mutations_sprite(runtime, source)
    expect_success(
        "layer set",
        {
            **_mutation_request(source, child_disabled),
            "target": {"layer_path": [3, 1]},
            "properties": {field: False},
        },
    )
    group = expect_success(
        "layer set",
        {
            **_mutation_request(child_disabled, group_disabled),
            "target": {"layer_path": [3]},
            "properties": {field: False},
        },
    )
    for phase in ("affected_before", "affected_after"):
        assert group[phase] == {"layer_paths": [[3]], "cels": []}
    assert all(
        frame["before_digest"] == frame["after_digest"]
        for frame in group["rendered_frames"]
    )


def test_regular_move_can_cross_tilemap_sibling_without_editing_its_content(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "moved.aseprite"
    lua = run_lua(FIXTURES / "tilemap_subtree.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "layer move",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [2, 2]},
            "stack_index": 1,
        },
    )
    assert [layer["name"] for layer in result["after"]["layers"][1]["children"]] == [
        "regular",
        "Tilemap 1",
    ]
    assert result["before"]["metadata"]["tileset_count"] == 1
    assert result["after"]["metadata"]["tileset_count"] == 1


def test_merge_reports_unlinked_surviving_cels_even_when_pixels_match(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "linked.aseprite"
    target = tmp_path / "merged.aseprite"
    lua = run_lua(FIXTURES / "linked_merge.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert native_link_status(runtime, source, tmp_path / "source-links.json") is True
    result = expect_success(
        "layer merge",
        {**_mutation_request(source, target), "target": {"layer_path": [2]}},
    )
    assert native_link_status(runtime, target, tmp_path / "target-links.json") is False
    for phase in ("affected_before", "affected_after"):
        assert {
            tuple(cel["layer_path"] + [cel["frame_number"]])
            for cel in result[phase]["cels"]
        } >= {
            (1, 1),
            (1, 2),
        }
