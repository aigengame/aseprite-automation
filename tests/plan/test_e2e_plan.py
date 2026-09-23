"""Installed Operation Plan behavior through the public CLI."""

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
