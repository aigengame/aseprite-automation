"""Replace Color has explicit Color Mode and byte-domain tolerance contracts."""

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from spa.authoring.raster.replace_color import ReplaceColorRequest
from tests.filter.test_unit_color_curve import payload as curve_payload


def payload(**changes):
    data = curve_payload()
    data.pop("points")
    color = {"kind": "rgba", "red": 100, "green": 60, "blue": 20, "alpha": 255}
    return {**data, "from": color, "to": color, "tolerance": 0, **changes}


@pytest.mark.parametrize(
    "changes",
    [
        {"tolerance": -1},
        {"tolerance": 256},
        {"tolerance": True},
        {"tolerance": 0.5},
        {"color_mode": "indexed", "palette_frame_number": 1},
        {"from": {"kind": "palette-index", "index": 1}},
        {"to": {"kind": "grayscale", "gray": 100, "alpha": 255}},
        {"channels": {"kind": "index"}},
        {"channels": {"kind": "components", "names": ["gray"]}},
        {"matched_pixel_count": True},
        {"application": {"kind": "pixels"}},
    ],
)
def test_inapplicable_input_is_rejected_before_native(changes):
    data = payload(**changes)
    with pytest.raises(ValidationError):
        ReplaceColorRequest.model_validate(data)
    assert not Draft202012Validator(ReplaceColorRequest.model_json_schema()).is_valid(
        data
    )


@pytest.mark.parametrize("tolerance", [0, 1, 255])
def test_equal_colors_remain_valid_and_serialize_using_public_from(tolerance):
    data = payload(tolerance=tolerance)
    request = ReplaceColorRequest.model_validate(data)
    assert request.model_dump()["from"] == data["from"]
    assert "from_color" not in request.model_dump()
    Draft202012Validator(ReplaceColorRequest.model_json_schema()).validate(data)


@pytest.mark.parametrize(
    "channels", [{"kind": "index"}, {"kind": "components", "names": ["red", "alpha"]}]
)
def test_both_indexed_channel_modes_accept_only_palette_index_colors(channels):
    data = payload(
        color_mode="indexed",
        channels=channels,
        palette_frame_number=1,
        **{
            "from": {"kind": "palette-index", "index": 0},
            "to": {"kind": "palette-index", "index": 255},
        },
    )
    ReplaceColorRequest.model_validate(data)
    Draft202012Validator(ReplaceColorRequest.model_json_schema()).validate(data)
