"""Public freehand Paint contracts and independently admitted algorithms."""

import json

import pytest

from tests.support import operation_services, runtime_observation, spa


def gesture_request() -> dict:
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        "opacity": 255,
        "brush": {"kind": "circle", "size": 1},
        "points": [{"x": 1, "y": 2}],
        "freehand_algorithm": "regular",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"points": []},
        {"points": [{"x": 0.5, "y": 0}]},
        {"freehand_algorithm": "smooth"},
        {"opacity": True},
        {"button": "left"},
        {"ink": "simple"},
        {"color": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 0}},
        {
            "behavior": {
                "kind": "erase",
                "foreground_color": {"kind": "palette-index", "index": 0},
            }
        },
        {
            "behavior": {
                "kind": "replace-foreground-with-background",
                "foreground_color": {"kind": "palette-index", "index": 1},
            }
        },
    ],
)
def test_eraser_rejects_ignored_or_invalid_gesture_inputs(change: dict) -> None:
    run = spa(
        "paint",
        "eraser",
        "--input-json",
        json.dumps(gesture_request() | {"behavior": {"kind": "erase"}} | change),
    )
    assert run.returncode == 2, run.stdout + run.stderr
    assert json.loads(run.stdout)["code"] == "invalid_request"


def test_unavailable_algorithm_does_not_hide_other_native_gestures() -> None:
    from spa.contracts import RuntimeRequest
    from spa.descriptors import schema_result

    result = schema_result(
        RuntimeRequest(),
        operation_services(
            lambda _: runtime_observation(
                "aseprite_runtime_introspection",
                "aseprite_paint_pencil",
                "aseprite_paint_pencil_dots",
                "aseprite_paint_eraser",
                "aseprite_paint_eraser_regular",
            )
        ),
    )
    assert {"spa paint pencil", "spa paint eraser"} <= {
        item.operation for item in result.operations
    }
    gaps = {gap.capability for gap in result.capability_gaps}
    assert "pencil regular" in gaps and "pencil pixel-perfect" in gaps
    assert "eraser dots" in gaps
    assert "pencil dots" not in gaps and "eraser regular" not in gaps
    assert {"Paint Dynamics", "Image Brush", "shading Ink"} <= gaps
