"""Copy, flatten, and validation through the installed Sprite commands."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _create(tmp_path: Path) -> Path:
    source = tmp_path / "source.aseprite"
    run = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "target_sprite_file": str(source),
                "width": 3,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {"kind": "transparent"},
                "overwrite": False,
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    return source


def _fixture(tmp_path: Path, name: str) -> Path:
    source = tmp_path / "source.aseprite"
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    with tempfile.TemporaryDirectory(prefix="spa-sprite-fixture-") as work:
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
                f"out={source}",
                "--script",
                str(Path(__file__).parent / "fixtures" / name),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr
    assert source.is_file()
    return source


def test_validate_reports_only_declared_checks_and_mismatches(tmp_path: Path) -> None:
    source = _create(tmp_path)
    run = spa(
        "sprite",
        "validate",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(source),
                "expected": {
                    "width": 3,
                    "height": 4,
                    "color_mode": "rgb",
                    "frame_count": 1,
                },
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(
        result,
        json.loads(spa("sprite", "validate", "--schema").stdout)["result_schema"],
    )
    assert result["operation"] == "spa sprite validate"
    assert result["status"] == "success"
    assert result["valid"] is False
    assert result["checks"] == [
        {"fact": "width", "expected": 3, "actual": 3, "matches": True},
        {"fact": "height", "expected": 4, "actual": 2, "matches": False},
        {"fact": "color_mode", "expected": "rgb", "actual": "rgb", "matches": True},
        {"fact": "frame_count", "expected": 1, "actual": 1, "matches": True},
    ]
    assert result["findings"] == [
        {
            "kind": "sprite_fact_mismatch",
            "subject": "sprite",
            "fact": "height",
            "expected": 4,
            "actual": 2,
        }
    ]


def test_copy_preserves_tile_bearing_native_bytes_and_reopens(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "tilemap_sprite.lua")
    target = tmp_path / "copied.aseprite"
    run = spa(
        "sprite",
        "copy",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": False,
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(
        result, json.loads(spa("sprite", "copy", "--schema").stdout)["result_schema"]
    )
    assert result["persisted_reopen_verified"] is True
    assert result["sprite"]["metadata"]["tileset_count"] > 0
    assert any(layer["is_tilemap"] for layer in result["sprite"]["layers"])
    assert target.read_bytes() == source.read_bytes()
    reopened = spa(
        "sprite",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(target),
                "inspection_scope": ["layers", "tilesets"],
            }
        ),
    )
    assert reopened.returncode == 0, reopened.stdout
    assert json.loads(reopened.stdout)["metadata"]["tileset_count"] > 0


def test_copy_requires_a_distinct_target_and_overwrite_permission(
    tmp_path: Path,
) -> None:
    source = _create(tmp_path)
    original = source.read_bytes()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(source),
        "overwrite": True,
    }
    same_target = spa("sprite", "copy", "--input-json", json.dumps(request))
    assert same_target.returncode != 0
    assert json.loads(same_target.stdout)["code"] == "invalid_request"
    assert source.read_bytes() == original

    target = tmp_path / "existing.aseprite"
    target.write_bytes(b"existing")
    request.update(target_sprite_file=str(target), overwrite=False)
    refused = spa("sprite", "copy", "--input-json", json.dumps(request))
    assert refused.returncode != 0
    assert json.loads(refused.stdout)["code"] == "target_commit_failed"
    assert target.read_bytes() == b"existing"
    assert source.read_bytes() == original
    assert not list(tmp_path.glob("*.staged.aseprite"))
