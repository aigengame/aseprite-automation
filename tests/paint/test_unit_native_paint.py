"""Native Paint input contracts through installed CLI schemas and validation."""

import json

import pytest
from jsonschema import Draft202012Validator

from tests.support import spa


def _request() -> dict:
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        "from": {"x": 0, "y": 0},
        "to": {"x": 1, "y": 1},
        "brush": {"kind": "circle", "size": 1},
        "color": {"kind": "rgba", "red": 255, "green": 0, "blue": 0, "alpha": 255},
        "opacity": 255,
        "ink": "simple",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"brush": {"kind": "circle", "size": 0}},
        {"brush": {"kind": "circle", "size": -1}},
        {"brush": {"kind": "circle", "size": 1, "angle": 0}},
        {"brush": {"kind": "square", "size": 1}},
        {"brush": {"kind": "line", "size": 1, "angle": 181}},
        {"brush": {"kind": "line", "size": 1, "angle": -181}},
        {"brush": {"kind": "square", "size": 1, "angle": 1.5}},
        {"brush": {"kind": "image", "size": 1}},
        {"opacity": -1},
        {"opacity": 256},
        {"opacity": True},
        {"from": {"x": 0.5, "y": 1}},
        {"stroke_width": 3},
        {"tool": "pencil"},
        {"points": [{"x": 0, "y": 0}]},
    ],
)
def test_invalid_native_line_input_fails_before_runtime(change: dict) -> None:
    run = spa("paint", "line", "--input-json", json.dumps(_request() | change))
    assert run.returncode == 2, run.stdout + run.stderr
    assert json.loads(run.stdout)["code"] == "invalid_request"


def test_shape_commands_share_one_request_schema_and_independent_runtime_gates() -> (
    None
):
    rectangle = json.loads(spa("paint", "rectangle", "--schema").stdout)
    ellipse = json.loads(spa("paint", "ellipse", "--schema").stdout)
    assert rectangle["request_schema"] == ellipse["request_schema"]
    assert rectangle["runtime_requirements"]["required_capabilities"] == [
        "aseprite_paint_rectangle"
    ]
    assert ellipse["runtime_requirements"]["required_capabilities"] == [
        "aseprite_paint_ellipse"
    ]
    schema = rectangle["request_schema"]
    Draft202012Validator.check_schema(schema)
    valid = _request()
    del valid["from"], valid["to"]
    valid |= {"bounds": {"x": -1, "y": -2, "width": 1, "height": 1}, "style": "outline"}
    validator = Draft202012Validator(schema)
    assert validator.is_valid(valid)
    for change in (
        {"bounds": {"x": 0, "y": 0, "width": 0, "height": 1}},
        {"style": "stroke"},
        {"rotation": 90},
    ):
        assert not validator.is_valid(valid | change)


def test_a_rectangle_capability_gap_keeps_line_and_ellipse_callable() -> None:
    from spa.contracts import RuntimeRequest
    from spa.descriptors import schema_result
    from tests.support import operation_services, runtime_observation

    result = schema_result(
        RuntimeRequest(),
        operation_services(
            lambda _: runtime_observation(
                "aseprite_runtime_introspection",
                "aseprite_paint_line",
                "aseprite_paint_ellipse",
            )
        ),
    )
    available = {operation.operation for operation in result.operations}
    assert "spa paint line" in available and "spa paint ellipse" in available
    assert "spa paint rectangle" not in available
    gap = next(
        gap for gap in result.capability_gaps if gap.capability == "spa paint rectangle"
    )
    assert "aseprite_paint_rectangle" in gap.evidence
