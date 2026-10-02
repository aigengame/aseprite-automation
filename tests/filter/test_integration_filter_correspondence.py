"""Filter publication requires evidence for the requested targets and Selection."""

import pytest

from spa.authoring.raster.despeckle import DespeckleRequest, despeckle
from spa.authoring.raster.filter import BrightnessContrastRequest, brightness_contrast
from spa.authoring.raster.hue_saturation import HueSaturationRequest, hue_saturation
from spa.authoring.raster.invert_outline import (
    InvertColorRequest,
    OutlineRequest,
    invert_color,
    outline,
)
from spa.contracts.ports import RuntimeIssue
from tests.filter.support import filter_cel_evidence, setup_filter_staging
from tests.filter.test_integration_despeckle import response_for
from tests.filter.test_integration_filter import evidence
from tests.filter.test_integration_hue_saturation import hue_evidence
from tests.filter.test_integration_pixel_filters import operation_case


@pytest.fixture(
    params=[
        "brightness-contrast",
        "hue-saturation",
        "color-curve",
        "replace-color",
        "invert-color",
        "outline",
        "despeckle",
    ]
)
def filter_case(request):
    name = request.param
    if name == "brightness-contrast":
        response, parameters = evidence(), {"brightness": 10, "contrast": 0}
        request_type, execute = BrightnessContrastRequest, brightness_contrast
    elif name == "hue-saturation":
        response = hue_evidence()
        parameters = {"adjustment": response["adjustment"]}
        request_type, execute = HueSaturationRequest, hue_saturation
    elif name in {"color-curve", "replace-color"}:
        response, parameters, request_type, execute = operation_case(name)
    elif name == "despeckle":
        response = response_for()
        parameters = {"width": 3, "height": 1, "tiled_mode": "none"}
        request_type, execute = DespeckleRequest, despeckle
    else:
        response, parameters = filter_cel_evidence(), {}
        del response["application"], response["palette_indexes"]
        request_type, execute = InvertColorRequest, invert_color
        if name == "outline":
            parameters = {
                "place": "outside",
                "outline_color": {
                    "kind": "rgba",
                    "red": 1,
                    "green": 2,
                    "blue": 3,
                    "alpha": 255,
                },
                "background_color": {
                    "kind": "rgba",
                    "red": 0,
                    "green": 0,
                    "blue": 0,
                    "alpha": 0,
                },
                "matrix": {"kind": "preset", "name": "circle"},
                "tiled_mode": "none",
            }
            response.update(parameters)
            request_type, execute = OutlineRequest, outline

    def request_for(source, target, **pixel_intent):
        pixels = {
            "color_mode": "rgb",
            "channels": {"kind": "components", "names": ["red"]},
            "cels_target": {"kind": "all"},
            **pixel_intent,
        }
        if name in {"brightness-contrast", "hue-saturation"}:
            intent = {"application": {"kind": "pixels", **pixels}}
        elif name == "despeckle":
            intent = {"pixels": pixels}
        else:
            intent = pixels
        return request_type.model_validate(
            {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": False,
                "overwrite": True,
                **parameters,
                **intent,
            }
        )

    return response, request_for, execute


@pytest.mark.parametrize("target_exists", [False, True])
@pytest.mark.parametrize("contradiction", ["omitted-selection", "selected-frame"])
def test_contradictory_targets_or_selection_cannot_publish(
    tmp_path, filter_case, target_exists, contradiction
):
    response, request_for, execute = filter_case
    intent = {}
    if contradiction == "omitted-selection":
        response["selection"] = {"kind": "empty"}
    else:
        response["cels_target_kind"] = "selected"
        intent["cels_target"] = {
            "kind": "selected",
            "layers": [{"layer_path": [1]}],
            "frame_numbers": [2],
        }
    services, source, target, staged = setup_filter_staging(tmp_path, response)
    if not target_exists:
        target.unlink()

    with pytest.raises(RuntimeIssue) as caught:
        execute(request_for(source, target, **intent), services)

    assert caught.value.kind == "response_malformed"
    assert source.read_bytes() == b"original source"
    if target_exists:
        assert target.read_bytes() == b"preexisting target"
    else:
        assert not target.exists()
    assert len(staged) == 1
    assert not staged[0].exists()


@pytest.mark.parametrize(
    "contradiction",
    [
        "duplicate-request",
        "duplicate-existing",
        "disagreement",
        "missing-existing",
        "empty-target",
    ],
)
def test_target_intersections_must_agree_before_publication(
    tmp_path, filter_case, contradiction
):
    response, request_for, execute = filter_case
    if contradiction == "duplicate-request":
        response["requested_intersections"] *= 2
    elif contradiction == "duplicate-existing":
        response["existing_target_cels"] *= 2
    elif contradiction == "disagreement":
        response["requested_intersections"] = [
            {"layer_path": [1], "frame_number": 1, "image_number": 2}
        ]
    elif contradiction == "missing-existing":
        response["existing_target_cels"] = []
    else:
        for key in (
            "requested_intersections",
            "existing_target_cels",
            "images",
            "processed_image_numbers",
            "affected_cels",
            "cel_effects",
        ):
            if key in response:
                response[key] = []
        response["changed"] = False
        if "changed_pixel_count" in response:
            response["changed_pixel_count"] = 0
    services, source, target, staged = setup_filter_staging(tmp_path, response)

    with pytest.raises(RuntimeIssue) as caught:
        execute(request_for(source, target), services)

    assert caught.value.kind == "response_malformed"
    assert source.read_bytes() == b"original source"
    assert target.read_bytes() == b"preexisting target"
    assert len(staged) == 1
    assert not staged[0].exists()
