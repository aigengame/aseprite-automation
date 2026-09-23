"""Static Plan preflight through the installed CLI."""

import json
import os
from pathlib import Path

from tests.support import spa


def test_plan_check_admits_a_read_plan_without_launching_aseprite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"unused by static preflight")
    request = {
        "plan": {
            "source_sprite_file": str(source),
            "steps": [
                {"operation": "sprite get", "input": {"inspection_scope": ["frames"]}}
            ],
        }
    }
    environment = os.environ | {"SPA_ASEPRITE_EXECUTABLE": "/missing/aseprite"}

    run = spa("plan", "check", "--input-json", json.dumps(request), env=environment)

    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["operation"] == "spa plan check"
    assert result["step_count"] == 1
    assert result["commit_required"] is False


def test_plan_check_rejects_unknown_step_and_operation_owned_pixel_limit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    cases = [
        [{"operation": "export image", "input": {}}],
        [
            {
                "operation": "paint apply",
                "input": {
                    "target": {"layer_path": [1], "frame_number": 1},
                    "patch": {
                        "coordinate_space": "image-pixel",
                        "rectangle": {"x": 0, "y": 0, "width": 257, "height": 1},
                        "runs": [
                            {
                                "x": 0,
                                "y": 0,
                                "length": 257,
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
            }
        ],
    ]
    for steps in cases:
        run = spa(
            "plan",
            "check",
            "--input-json",
            json.dumps(
                {
                    "plan": {
                        "source_sprite_file": str(source),
                        "target_sprite_file": str(tmp_path / "target.aseprite"),
                        "steps": steps,
                    },
                }
            ),
            env=os.environ | {"SPA_ASEPRITE_EXECUTABLE": "/missing/aseprite"},
        )
        assert run.returncode == 2, run.stdout
        assert json.loads(run.stdout)["code"] == "invalid_request"


def test_plan_step_limit_admits_the_issue_reference_size(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    steps = [{"operation": "sprite get", "input": {"inspection_scope": ["frames"]}}]
    for count, expected in ((42, 0), (65, 2)):
        run = spa(
            "plan",
            "check",
            "--input-json",
            json.dumps(
                {
                    "plan": {"source_sprite_file": str(source), "steps": steps * count},
                }
            ),
            env=os.environ | {"SPA_ASEPRITE_EXECUTABLE": "/missing/aseprite"},
        )
        assert run.returncode == expected, run.stdout
