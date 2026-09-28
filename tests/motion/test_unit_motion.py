"""Public motion input boundaries, before any native invocation."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from spa.motion import MotionInput
from tests.motion.test_e2e_motion import curves


def test_full_signed_coordinate_displacement_is_accepted() -> None:
    request = curves()
    request["position_offsets"]["keys"][0]["offset"] = {"x": -65535, "y": 65535}
    request["position_offsets"]["keys"][1]["offset"] = {"x": 65535, "y": -65535}
    parsed = MotionInput.model_validate(request)
    assert parsed.position_offsets.keys[0].offset.x == -65535
    assert parsed.position_offsets.keys[-1].offset.y == -65535


@pytest.mark.parametrize("bad", [-65536, 65536, 0.5, "1", True])
def test_offset_domain_rejects_out_of_range_or_non_integer_values(bad: object) -> None:
    request = curves()
    request["position_offsets"]["keys"][0]["offset"]["x"] = bad
    with pytest.raises(ValidationError):
        MotionInput.model_validate(request)


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value["position_offsets"]["keys"].pop(),
        lambda value: value["position_offsets"]["keys"].insert(
            1, deepcopy(value["position_offsets"]["keys"][0])
        ),
        lambda value: value["position_offsets"]["keys"].reverse(),
        lambda value: value["position_offsets"]["keys"][0].update(frame_number=2),
        lambda value: value["opacity"]["keys"][-1].update(frame_number=6),
        lambda value: value.update(from_frame=5, to_frame=1),
        lambda value: value.update(position_offsets=None, opacity=None),
        lambda value: value["position_offsets"].pop("rounding"),
        lambda value: value["opacity"].pop("interpolation"),
    ],
)
def test_incomplete_unordered_or_unspecified_curves_are_rejected(change) -> None:
    request = curves()
    change(request)
    with pytest.raises(ValidationError):
        MotionInput.model_validate(request)


def test_single_frame_requires_one_key_per_supplied_curve() -> None:
    request = curves()
    request.update(from_frame=3, to_frame=3)
    request["position_offsets"]["keys"] = [
        {"frame_number": 3, "offset": {"x": -2, "y": 3}}
    ]
    request["opacity"]["keys"] = [{"frame_number": 3, "opacity": 0}]
    assert MotionInput.model_validate(request).to_frame == 3
    request["opacity"]["keys"].append({"frame_number": 3, "opacity": 255})
    with pytest.raises(ValidationError):
        MotionInput.model_validate(request)
