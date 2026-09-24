"""Layer mutations through the installed CLI and real Aseprite."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _fixture(target: Path, name: str = "mutations.lua") -> None:
    aseprite = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    resource = aseprite.parent.parent / "Resources" / "data" / "gui.xml"
    script = Path(__file__).parent / "fixtures" / name
    with tempfile.TemporaryDirectory(prefix="spa-layer-mutation-fixture-") as work:
        prepared = prepare_invocation(aseprite, resource, Path(work))
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={target}",
                "--script",
                str(script),
            ],
            text=True,
            capture_output=True,
            env=prepared.environment,
            check=False,
        )
    assert run.returncode == 0, run.stderr


def _run(command: str, request: dict[str, object]) -> tuple[int, dict]:
    result = spa(
        "layer",
        command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    return result.returncode, json.loads(result.stdout)


def _mutation_request(source: Path, target: Path) -> dict[str, object]:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
    }


def test_set_layer_properties_and_report_rendered_change(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source)
    code, result = _run(
        "set",
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
    assert code == 0, result
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
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "moved.aseprite"
    _fixture(source)
    code, result = _run(
        "move",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [2]},
            "stack_index": 1,
        },
    )
    assert code == 0, result
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


def test_remove_group_reports_complete_deleted_subtree_and_cels(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "removed.aseprite"
    _fixture(source)
    code, result = _run(
        "remove",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [3]},
        },
    )
    assert code == 0, result
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
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "merged.aseprite"
    _fixture(source)
    code, result = _run(
        "merge",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [2]},
        },
    )
    assert code == 0, result
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
    tmp_path: Path, command: str, details: dict, expected_code: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "rejected.aseprite"
    _fixture(source)
    code, result = _run(command, {**_mutation_request(source, target), **details})
    assert code == 2, result
    assert result["code"] == expected_code
    assert not target.exists()


def test_remove_rejects_group_containing_tilemap(tmp_path: Path) -> None:
    source = tmp_path / "tilemap.aseprite"
    target = tmp_path / "rejected.aseprite"
    _fixture(source, "tilemap_subtree.lua")
    code, result = _run(
        "remove",
        {**_mutation_request(source, target), "target": {"layer_path": [2]}},
    )
    assert code == 2, result
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
    tmp_path: Path, command: str, extra: dict
) -> None:
    source = tmp_path / "unsupported.aseprite"
    target = tmp_path / "rejected.aseprite"
    _fixture(source, "tilemap_subtree.lua")
    code, result = _run(
        command,
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [1]},
            **extra,
        },
    )
    assert code == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert not target.exists()


def test_merge_compositing_ignores_both_ambient_preference_values(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, "merge_composite.lua")
    aseprite = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    resource = aseprite.parent.parent / "Resources" / "data" / "gui.xml"
    kernel = Path(__file__).parents[2] / "src" / "spa" / "kernel"
    script = Path(__file__).parent / "fixtures" / "merge_under_ambient.lua"
    reports = []
    for ambient in (False, True):
        target = tmp_path / f"merged-{ambient}.aseprite"
        report = tmp_path / f"merged-{ambient}.json"
        with tempfile.TemporaryDirectory(prefix="spa-layer-merge-ambient-") as work:
            prepared = prepare_invocation(aseprite, resource, Path(work))
            params = {
                "ambient": str(ambient).lower(),
                "source": str(source),
                "target": str(target),
                "report": str(report),
                "inspection": str(kernel / "sprite_inspect.lua"),
                "layer_select": str(kernel / "layer_select.lua"),
                "mutation": str(kernel / "layer_mutation_support.lua"),
                "digest": str(kernel / "digest.lua"),
                "persistence": str(kernel / "sprite_persistence.lua"),
                "workspace": str(work),
            }
            command = [str(prepared.executable), "--batch"]
            for key, value in params.items():
                command.extend(["--script-param", f"{key}={value}"])
            command.extend(["--script", str(script)])
            run = subprocess.run(
                command,
                text=True,
                capture_output=True,
                env=prepared.environment,
                check=False,
            )
        assert run.returncode == 0, run.stdout + run.stderr
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
    tmp_path: Path,
) -> None:
    source = tmp_path / "nested.aseprite"
    moved = tmp_path / "moved.aseprite"
    merged = tmp_path / "merged.aseprite"
    _fixture(source, "nested_mutations.lua")
    code, move = _run(
        "move",
        {
            **_mutation_request(source, moved),
            "target": {"layer_path": [2, 2]},
            "stack_index": 1,
        },
    )
    assert code == 0, move
    assert [layer["name"] for layer in move["after"]["layers"][1]["children"]] == [
        "nested-upper",
        "nested-lower",
    ]
    assert [2, 1] in move["affected_after"]["layer_paths"]
    assert [2, 2] in move["affected_after"]["layer_paths"]

    code, merge = _run(
        "merge",
        {
            **_mutation_request(source, merged),
            "target": {"layer_path": [2, 2]},
        },
    )
    assert code == 0, merge
    assert [layer["name"] for layer in merge["after"]["layers"][1]["children"]] == [
        "nested-lower"
    ]
    assert merge["after"]["metadata"]["layer_count"] == 3
    assert [2, 1] in merge["affected_after"]["layer_paths"]


def test_set_group_properties_without_image_only_fields(tmp_path: Path) -> None:
    source = tmp_path / "nested.aseprite"
    target = tmp_path / "group-set.aseprite"
    _fixture(source, "nested_mutations.lua")
    code, result = _run(
        "set",
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
    assert code == 0, result
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
    tmp_path: Path, path: list[int], name: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "renamed.aseprite"
    _fixture(source)
    code, result = _run(
        "set",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": path},
            "properties": {"name": name},
        },
    )
    assert code == 0, result
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
    tmp_path: Path, command: str, extra: dict
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "noop.aseprite"
    _fixture(source)
    code, result = _run(
        command,
        {**_mutation_request(source, target), "target": {"layer_path": [2]}, **extra},
    )
    assert code == 0, result
    for phase in ("affected_before", "affected_after"):
        assert result[phase] == {"layer_paths": [], "cels": []}
    assert all(
        frame["before_digest"] == frame["after_digest"]
        for frame in result["rendered_frames"]
    )


def test_move_rejects_crossing_background_before_publishing(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "rejected.aseprite"
    _fixture(source, "tilemap_subtree.lua")
    code, result = _run(
        "move",
        {
            **_mutation_request(source, target),
            "target": {"layer_path": [2]},
            "stack_index": 1,
        },
    )
    assert code == 2, result
    assert result["code"] == "layer_invalid_position"
    assert not target.exists()
