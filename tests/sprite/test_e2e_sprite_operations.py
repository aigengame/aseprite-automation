"""Copy, flatten, and validation through the installed Sprite commands."""

import json
import os
from pathlib import Path

import pytest
from jsonschema import validate

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
