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


def _fixture(target: Path) -> None:
    aseprite = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    resource = aseprite.parent.parent / "Resources" / "data" / "gui.xml"
    script = Path(__file__).parent / "fixtures" / "mutations.lua"
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


def test_move_reorders_one_sibling_and_reports_shifted_addresses(tmp_path: Path) -> None:
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
    assert result["rendered_frames"][0]["before_digest"] != result[
        "rendered_frames"
    ][0]["after_digest"]


def test_merge_down_preserves_lower_identity_and_persisted_pixels(tmp_path: Path) -> None:
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
