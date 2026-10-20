"""Request builders that more than one Plan e2e module uses."""

from pathlib import Path
from typing import Any

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


def plan_request(source: Path, target: Path, steps: list[dict]) -> dict[str, Any]:
    """Return a `plan run` request that runs steps from source to target.

    `in_place` is true when target is source, and `overwrite` is true when target
    already exists.
    """
    return {
        "plan": {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": source == target,
            "overwrite": target.exists(),
            "steps": steps,
        }
    }
