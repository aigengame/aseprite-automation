"""Color Curve request boundaries are explicit before any native invocation."""

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from spa.authoring.raster.color_curve import ColorCurveRequest


def payload(**changes):
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "color_mode": "rgb",
        "channels": {"kind": "components", "names": ["red"]},
        "cels_target": {"kind": "all"},
        "points": [{"input": 0, "output": 255}],
        **changes,
    }


@pytest.mark.parametrize(
    "points",
    [
        [],
        [{"input": -1, "output": 0}],
        [{"input": 0, "output": 256}],
        [{"input": True, "output": 0}],
        [{"input": 0, "output": 1.5}],
    ],
)
def test_invalid_point_shape_is_rejected_by_request_and_schema(points):
    data = payload(points=points)
    with pytest.raises(ValidationError):
        ColorCurveRequest.model_validate(data)
    assert not Draft202012Validator(ColorCurveRequest.model_json_schema()).is_valid(
        data
    )


@pytest.mark.parametrize("inputs", [[10, 10], [10, 9]])
def test_curve_order_is_rejected_without_sorting(inputs):
    with pytest.raises(ValidationError, match="strictly increase"):
        ColorCurveRequest.model_validate(
            payload(points=[{"input": value, "output": 0} for value in inputs])
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"channels": {"kind": "index"}},
        {"channels": {"kind": "components", "names": ["gray"]}},
        {"channels": {"kind": "components", "names": []}},
        {"color_mode": "grayscale"},
        {"color_mode": "indexed"},
        {"palette_frame_number": 1},
        {"application": {"kind": "pixels"}},
        {"tiled_mode": "none"},
    ],
)
def test_inapplicable_options_are_absent_from_the_public_contract(changes):
    data = payload(**changes)
    with pytest.raises(ValidationError):
        ColorCurveRequest.model_validate(data)
    assert not Draft202012Validator(ColorCurveRequest.model_json_schema()).is_valid(
        data
    )


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {
            "color_mode": "grayscale",
            "channels": {"kind": "components", "names": ["gray", "alpha"]},
        },
        {
            "color_mode": "indexed",
            "channels": {"kind": "index"},
            "palette_frame_number": 1,
        },
        {
            "color_mode": "indexed",
            "channels": {"kind": "components", "names": ["alpha", "blue"]},
            "palette_frame_number": 2,
        },
    ],
)
def test_explicit_pixel_modes_accept_constant_and_nonmonotonic_curves(changes):
    data = payload(**changes)
    ColorCurveRequest.model_validate(data)
    Draft202012Validator(ColorCurveRequest.model_json_schema()).validate(data)
    data["points"] = [
        {"input": 10, "output": 255},
        {"input": 100, "output": 0},
        {"input": 200, "output": 255},
    ]
    ColorCurveRequest.model_validate(data)
