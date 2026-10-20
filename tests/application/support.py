"""Standalone mutation completion cases that the e2e and integration tiers share."""

from pathlib import Path
from typing import Any

from tests.support import motion_curves

OPERATIONS = (
    "cel set",
    "motion apply",
    "tag add",
    "frame set",
    "cel remove",
    "layer set",
    "image flip",
    "image resize",
    "image replace",
    "paint composite",
)
"""Standalone mutations that a posed motion Sprite accepts."""

_ADDRESS = {"layer": {"layer_path": [1]}, "frame_number": 1}
_IMAGE_INPUT = {
    "kind": "inline",
    "snapshot": {
        "coordinate_space": "image-pixel",
        "color_mode": "rgb",
        "rectangle": {"x": 0, "y": 0, "width": 9, "height": 12},
        "rows": [
            [
                {
                    "length": 9,
                    "color": {
                        "kind": "rgba",
                        "red": 210,
                        "green": 50,
                        "blue": 20,
                        "alpha": 255,
                    },
                }
            ]
            for _ in range(12)
        ],
    },
}


def completion_request(
    operation: str, source: Path, target: Path, in_place: bool
) -> dict[str, Any]:
    """Return a request of operation that may overwrite target.

    The request has no `aseprite`; `observe_cli` adds it.
    """
    inputs = {
        "motion apply": motion_curves(),
        "tag add": {
            "name": "new",
            "from_frame": 1,
            "to_frame": 2,
            "direction": "forward",
            "repeats": 0,
        },
        "cel set": {"target": _ADDRESS, "opacity": 42},
        "frame set": {"frame_number": 1, "duration_ms": 321},
        "cel remove": {"target": _ADDRESS},
        "layer set": {"target": _ADDRESS["layer"], "properties": {"opacity": 128}},
        "image flip": {"target": _ADDRESS, "axis": "horizontal"},
        "image resize": {
            "target": _ADDRESS,
            "width": 5,
            "height": 6,
            "method": "nearest-neighbor",
            "position_policy": {"kind": "keep"},
        },
        "image replace": {"target": _ADDRESS, "input": _IMAGE_INPUT},
        "paint composite": {
            "target": _ADDRESS,
            "input": _IMAGE_INPUT,
            "position": {"x": 0, "y": 0},
            "opacity": 255,
            "blend_mode": "normal",
        },
    }[operation]
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": in_place,
        "overwrite": True,
        **inputs,
    }


def assert_completion_trace(
    observed: dict[str, Any], operation: str, case: str, tmp_path: Path
) -> None:
    """Check the completion events of case, and that no staged file remains."""
    # These Operations have no capability-enrichment probe at the CLI boundary.
    preflight_first = operation in ("frame set", "paint composite")
    expected_events = ["identity", "probe"] if preflight_first else ["probe"]
    if case != "probe":
        if not preflight_first:
            expected_events.append("identity")
        expected_events.extend(["stage", "invoke"])
        if case in ("success", "identity", "commit"):
            expected_events.append("identity")
        if case in ("success", "commit"):
            expected_events.append("commit")
        expected_events.append("discard")
        assert observed["discarded"] is True
        assert not Path(observed["staged"]).exists()
    assert observed["events"] == expected_events
    assert observed["native_invocations"] == int(case not in ("probe", "invocation"))
    assert not list(tmp_path.glob(".*.staged.aseprite"))
