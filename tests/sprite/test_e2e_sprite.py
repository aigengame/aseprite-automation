"""Installed Sprite Operations against a real Aseprite executable."""

import json
import os
import subprocess
import tempfile
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import validate

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import spa

pytestmark = pytest.mark.e2e


def _populated_sprite(target: Path) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]),
        PROBE_RESOURCES,
    )
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


def _create(
    target: Path, initial_layer: dict[str, object], *, overwrite: bool = False
) -> dict[str, object]:
    request = {
        "target_sprite_file": str(target),
        "width": 3,
        "height": 2,
        "color_mode": "rgb",
        "initial_layer": initial_layer,
        "overwrite": overwrite,
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
    assert result["persisted_initial_layer"] == initial_layer
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

    color = {"red": 17, "green": 34, "blue": 51, "alpha": 255}
    background = _create(
        tmp_path / "background.aseprite",
        {"kind": "background", "background_color": color},
    )
    background_layer = background["sprite"]["layers"][0]
    assert background_layer["is_transparent"] is False
    assert background_layer["is_background"] is True


def test_background_postcondition_rejects_a_nonuniform_reopened_fill(
    tmp_path: Path,
) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]),
        PROBE_RESOURCES,
    )
    fixture = Path(__file__).parent / "fixtures" / "reject_nonuniform_background.lua"
    target = tmp_path / "nonuniform-background.aseprite"
    response = tmp_path / "verification.json"
    with tempfile.TemporaryDirectory(prefix="spa-background-postcondition-") as work:
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
                f"creation={files('spa.kernel').joinpath('sprite_create_support.lua')}",
                "--script-param",
                f"target={target}",
                "--script-param",
                f"response={response}",
                "--script",
                str(fixture),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )

    assert run.returncode == 0, run.stderr
    verification = json.loads(response.read_text(encoding="utf-8"))
    assert verification["accepted"] is False
    assert "Background fill differs" in verification["message"]


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


def test_wheel_installed_handler_rejection_is_schema_valid_without_target_commit(
    tmp_path: Path,
) -> None:
    installed_cli = os.environ.get("SPA_TEST_INSTALLED_CLI")
    if installed_cli is None:
        pytest.skip("SPA_TEST_INSTALLED_CLI does not select a wheel-installed CLI")
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("occupied", encoding="utf-8")
    target = parent_file / "never-committed.aseprite"
    request = {
        "target_sprite_file": str(target),
        "width": 3,
        "height": 2,
        "color_mode": "rgb",
        "initial_layer": {"kind": "transparent"},
        "overwrite": False,
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }
    run = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(request),
        executable=installed_cli,
    )
    assert run.returncode == 1, run.stdout
    failure = json.loads(run.stdout)
    schema = json.loads(
        spa("sprite", "create", "--schema", executable=installed_cli).stdout
    )
    validate(failure, schema["failure_schema"])
    assert failure["code"] == "kernel_execution_failed"
    assert failure["details"]["kind"] == "kernel_execution"
    assert "target_commit" not in failure
    assert parent_file.read_text(encoding="utf-8") == "occupied"
    assert not target.exists()


def test_invalid_existing_target_fails_without_target_commit(tmp_path: Path) -> None:
    target = tmp_path / "directory.aseprite"
    target.mkdir()
    request = {
        "target_sprite_file": str(target),
        "width": 3,
        "height": 2,
        "color_mode": "rgb",
        "initial_layer": {"kind": "transparent"},
        "overwrite": False,
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }
    run = spa("sprite", "create", "--input-json", json.dumps(request))
    assert run.returncode == 1, run.stdout
    failure = json.loads(run.stdout)
    validate(
        failure,
        json.loads(spa("sprite", "create", "--schema").stdout)["failure_schema"],
    )
    assert failure["code"] == "target_commit_failed"
    assert failure["details"] == {
        "kind": "target_commit",
        "target_sprite_file": str(target),
        "reason": "target_not_file",
    }
    assert "target_commit" not in failure
    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_create_requires_explicit_permission_to_replace_an_existing_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing.aseprite"
    target.write_bytes(b"existing")
    request = {
        "target_sprite_file": str(target),
        "width": 3,
        "height": 2,
        "color_mode": "rgb",
        "initial_layer": {"kind": "transparent"},
        "overwrite": False,
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }

    refused = spa("sprite", "create", "--input-json", json.dumps(request))

    assert refused.returncode == 1, refused.stdout
    failure = json.loads(refused.stdout)
    assert failure["code"] == "target_commit_failed"
    assert failure["details"]["reason"] == "overwrite_not_allowed"
    assert target.read_bytes() == b"existing"

    replaced = _create(target, {"kind": "transparent"}, overwrite=True)
    assert replaced["target_commit"]["target_sprite_file"] == str(target)
    assert target.read_bytes() != b"existing"


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
    assert group["is_group"] is True
    assert group["is_image"] is False
    assert [child["name"] for child in group["children"]] == ["outline"]
    assert group["children"][0]["is_image"] is True
    assert group["children"][0]["is_group"] is False
    child_path = group["children"][0]["path"]
    child_cel = next(cel for cel in result["cels"] if cel["layer_path"] == child_path)
    assert child_cel["frame_number"] == 2
    assert child_cel["bounds"] == {"x": 4, "y": 2, "width": 2, "height": 3}
    assert child_cel["opacity"] == 123
    assert child_cel["z_index"] == 4
    assert result["slices"] == [
        {
            "name": "panel",
            "data": "panel-data",
            "keys": [
                {
                    "frame_number": 1,
                    "bounds": {"x": 1, "y": 2, "width": 3, "height": 4},
                    "center": {"x": 1, "y": 1, "width": 1, "height": 2},
                    "pivot": {"x": 2, "y": 3},
                }
            ],
        }
    ]
    assert result["scope"]["complete_sections"] == sections
    assert result["tilesets"] == [
        {
            "name": "terrain",
            "tile_count": 2,
            "base_index": 7,
            "grid_origin": {"x": 0, "y": 0},
            "tile_size": {"width": 4, "height": 5},
        }
    ]
