"""Explicit orientation intent is validated before the runtime is selected."""

import json

import pytest
from jsonschema import validate

from tests.support import spa


@pytest.mark.parametrize(
    ("operation", "options"),
    [
        ("flip", {}),
        ("flip", {"axis": "diagonal"}),
        ("flip", {"axis": "horizontal", "selection": "active"}),
        ("rotate", {"position_policy": {"kind": "keep"}}),
        ("rotate", {"angle": 90}),
        *[
            ("rotate", {"angle": angle, "position_policy": {"kind": "keep"}})
            for angle in (0, 45, 270, -180, 360, 450, 90.0, "90", True)
        ],
        *[
            ("rotate", {"angle": 90, "position_policy": policy})
            for policy in (
                {"kind": "center"},
                {"kind": "pivot", "pivot_x": 1},
                {"kind": "pivot", "pivot_x": 1.5, "pivot_y": 0},
                {"kind": "pivot", "pivot_x": True, "pivot_y": 0},
                {"kind": "pivot", "pivot_x": 2**31, "pivot_y": 0},
                {"kind": "pivot", "pivot_x": 0, "pivot_y": 0, "rounding": "floor"},
            )
        ],
    ],
)
def test_orientation_requires_exact_intent_before_runtime_access(
    operation: str, options: dict
) -> None:
    request = {
        "source_sprite_file": "missing-source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "aseprite": "/missing/aseprite",
        **options,
    }
    run = spa("image", operation, "--input-json", json.dumps(request))
    result = json.loads(run.stdout)
    assert run.returncode == 2, result
    assert result["code"] == "invalid_request"
    schema = json.loads(spa("image", operation, "--schema").stdout)
    validate(result, schema["failure_schema"])
