"""Installed Sprite Operations against a real Aseprite executable."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts import RuntimeRequest
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _populated_sprite(target: Path) -> None:
    observation = probe(RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]))
    fixture = Path(__file__).parent / "fixtures" / "populated_sprite.lua"
    with tempfile.TemporaryDirectory(prefix="spa-populated-fixture-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={target}",
                "--script",
                str(fixture),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr
    assert target.is_file()


def _create(target: Path, initial_layer: dict[str, object]) -> dict[str, object]:
    request = {
        "target_sprite_file": str(target),
        "width": 3,
        "height": 2,
        "color_mode": "rgb",
        "initial_layer": initial_layer,
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }
    run = spa("sprite", "create", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(
        result, json.loads(spa("sprite", "create", "--schema").stdout)["result_schema"]
    )
    assert target.is_file()
    assert result["target_commit"]["target_sprite_file"] == str(target)
    assert result["target_commit"]["byte_size"] == target.stat().st_size
    assert len(result["target_commit"]["sha256"]) == 64
    assert result["persisted_reopen_verified"] is True
    assert result["sprite"]["metadata"]["width"] == 3
    assert result["sprite"]["metadata"]["height"] == 2
    assert result["sprite"]["metadata"]["color_mode"] == "rgb"
    return result


def test_create_persists_explicit_transparent_and_background_layer_choices(
    tmp_path: Path,
) -> None:
    transparent = _create(tmp_path / "transparent.aseprite", {"kind": "transparent"})
    transparent_layer = transparent["sprite"]["layers"][0]
    assert transparent_layer["is_transparent"] is True
    assert transparent_layer["is_background"] is False
    assert transparent_layer["background_color"] is None

    color = {"red": 17, "green": 34, "blue": 51, "alpha": 255}
    background = _create(
        tmp_path / "background.aseprite",
        {"kind": "background", "background_color": color},
    )
    background_layer = background["sprite"]["layers"][0]
    assert background_layer["is_transparent"] is False
    assert background_layer["is_background"] is True
    assert background_layer["background_color"] == color


def test_get_reports_complete_requested_sections_and_explicit_omissions(
    tmp_path: Path,
) -> None:
    target = tmp_path / "inspect.aseprite"
    _create(target, {"kind": "transparent"})
    sections = ["frames", "tags", "palettes", "layers", "cels", "slices", "tilesets"]
    run = spa(
        "sprite",
        "get",
        "--input-json",
        json.dumps(
            {
                "sprite_file": str(target),
                "inspection_scope": sections,
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(
        result, json.loads(spa("sprite", "get", "--schema").stdout)["result_schema"]
    )
    assert result["scope"] == {
        "requested_sections": sections,
        "complete_sections": sections,
        "unrequested_sections": [],
    }
    assert result["metadata"]["width"] == 3
    assert result["metadata"]["height"] == 2
    assert result["metadata"]["color_mode"] == "rgb"
    assert result["frames"] == [{"frame_number": 1, "duration_ms": 100}]
    assert result["tags"] == []
    assert len(result["palettes"]) == 1
    assert result["palettes"][0]["entries"]
    assert [entry["index"] for entry in result["palettes"][0]["entries"]] == list(
        range(len(result["palettes"][0]["entries"]))
    )
    assert len(result["layers"]) == 1
    assert len(result["cels"]) == 1
    assert result["slices"] == []
    assert result["tilesets"] == []

    partial = spa(
        "sprite",
        "get",
        "--input-json",
        json.dumps(
            {
                "sprite_file": str(target),
                "inspection_scope": ["frames"],
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert partial.returncode == 0, partial.stdout
    partial_result = json.loads(partial.stdout)
    assert partial_result["scope"]["complete_sections"] == ["frames"]
    assert partial_result["scope"]["unrequested_sections"] == [
        "tags",
        "palettes",
        "layers",
        "cels",
        "slices",
        "tilesets",
    ]
    for section in partial_result["scope"]["unrequested_sections"]:
        assert partial_result[section] is None


def test_handler_rejection_is_schema_valid_and_does_not_publish_target(
    tmp_path: Path,
) -> None:
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("occupied", encoding="utf-8")
    target = parent_file / "never-committed.aseprite"
    request = {
        "target_sprite_file": str(target),
        "width": 3,
        "height": 2,
        "color_mode": "rgb",
        "initial_layer": {"kind": "transparent"},
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }
    run = spa("sprite", "create", "--input-json", json.dumps(request))
    assert run.returncode == 1, run.stdout
    failure = json.loads(run.stdout)
    schema = json.loads(spa("sprite", "create", "--schema").stdout)
    validate(failure, schema["failure_schema"])
    assert failure["code"] == "kernel_execution_failed"
    assert failure["details"]["kind"] == "kernel_execution"
    assert "target_commit" not in failure
    assert parent_file.read_text(encoding="utf-8") == "occupied"
    assert not target.exists()


def test_get_reports_populated_native_structures_completely(tmp_path: Path) -> None:
    target = tmp_path / "populated.aseprite"
    _populated_sprite(target)
    sections = ["frames", "tags", "palettes", "layers", "cels", "slices", "tilesets"]
    run = spa(
        "sprite",
        "get",
        "--input-json",
        json.dumps(
            {
                "sprite_file": str(target),
                "inspection_scope": sections,
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["frames"] == [
        {"frame_number": 1, "duration_ms": 120},
        {"frame_number": 2, "duration_ms": 340},
    ]
    assert result["tags"] == [
        {
            "name": "walk",
            "from_frame": 1,
            "to_frame": 2,
            "direction": "ping_pong",
            "repeats": 2,
            "color": {"red": 10, "green": 20, "blue": 30, "alpha": 255},
        }
    ]
    group = next(layer for layer in result["layers"] if layer["name"] == "body")
    assert [child["name"] for child in group["children"]] == ["outline"]
    child_path = group["children"][0]["path"]
    child_cel = next(cel for cel in result["cels"] if cel["layer_path"] == child_path)
    assert child_cel["frame_number"] == 2
    assert child_cel["bounds"] == {"x": 4, "y": 2, "width": 2, "height": 3}
    assert child_cel["opacity"] == 123
    assert child_cel["z_index"] == 4
    assert result["slices"] == [
        {
            "name": "panel",
            "bounds": {"x": 1, "y": 2, "width": 3, "height": 4},
            "center": {"x": 1, "y": 1, "width": 1, "height": 2},
            "pivot": {"x": 2, "y": 3},
        }
    ]
    assert result["tilesets"] == [
        {
            "name": "terrain",
            "tile_count": 2,
            "base_index": 7,
            "grid_origin": {"x": 0, "y": 0},
            "tile_size": {"width": 4, "height": 5},
        }
    ]
