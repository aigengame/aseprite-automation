"""Tileset composition preflight through the public Plan boundary."""

import json
from pathlib import Path

from tests.support import spa


def test_plan_check_admits_rebind_then_remove(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"Static Plan preflight does not read native content")
    result = spa(
        "plan",
        "check",
        "--input-json",
        json.dumps(
            {
                "plan": {
                    "source_sprite_file": str(source),
                    "target_sprite_file": str(target),
                    "steps": [
                        {
                            "operation": "layer set-tileset",
                            "input": {
                                "layer": {"layer_name": "map"},
                                "target": {"tileset_name": "replacement"},
                                "mapping": {"kind": "by_key"},
                                "grid_policy": "require_equal",
                            },
                        },
                        {
                            "operation": "tileset remove",
                            "input": {
                                "target": {"tileset_name": "terrain"},
                            },
                        },
                    ],
                }
            }
        ),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    accepted = json.loads(result.stdout)
    assert accepted["step_count"] == 2
    assert accepted["commit_required"] is True
    assert not target.exists()
