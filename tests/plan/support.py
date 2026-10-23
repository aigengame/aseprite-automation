"""Request builders and the Plan observer that more than one Plan e2e module uses."""

import subprocess
from pathlib import Path
from typing import Any

from tests.support import observe_cli

FIXTURES = Path(__file__).parent / "fixtures"


def red_pixel(x: int = 0) -> dict[str, object]:
    """Return a `paint apply` input that paints one red pixel at (x, 0) of [1]@1."""
    return {
        "target": {"layer_path": [1], "frame_number": 1},
        "patch": {
            "coordinate_space": "image-pixel",
            "rectangle": {"x": x, "y": 0, "width": 1, "height": 1},
            "runs": [
                {
                    "x": x,
                    "y": 0,
                    "length": 1,
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
    }


def plan_request(
    source: Path | None, target: Path | None, steps: list[dict]
) -> dict[str, Any]:
    """Return a `plan run` request that runs steps from source to target.

    source is None for a Plan that creates its Sprite, and target is None for a Plan
    that only reads. `in_place` is true when target is source, and `overwrite` is
    true when target already exists.
    """
    body: dict[str, Any] = {}
    if source is not None:
        body["source_sprite_file"] = str(source)
    if target is not None:
        body["target_sprite_file"] = str(target)
        body["in_place"] = source == target
        body["overwrite"] = target.exists()
    body["steps"] = steps
    return {"plan": body}


def observe_plan(
    case: str, request: dict[str, Any], tmp_path: Path
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], dict[str, Any]]:
    """Run `spa plan run` with request in the observer, at the "invoke_direct" seam.

    The observer counts the native invocations and Target Commits, and changes the
    native Plan response as case requires (`tests/fixtures/observe_cli.py`). The
    request must name a Target. This asserts the rules of each Plan run: one native
    invocation, one Target Commit when the Plan succeeds and none when it fails, and
    no staged file in tmp_path. Return the process, its envelope, and the
    observations.
    """
    process, envelope, observations = observe_cli(
        case, "plan run", request, tmp_path / "observations.json", seam="invoke_direct"
    )
    assert observations["native_invocations"] == 1, observations
    assert observations["commits"] == int(process.returncode == 0), observations
    assert not list(tmp_path.glob(".*.staged.aseprite"))
    return process, envelope, observations
