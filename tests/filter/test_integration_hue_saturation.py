"""Hue/Saturation publishes only request-matched native persistence evidence."""

import pytest

from spa.authoring.raster.hue_saturation import HueSaturationRequest, hue_saturation
from spa.contracts.ports import RuntimeIssue
from tests.filter.support import assert_unpublished, filter_cel_evidence
from tests.filter.test_integration_filter import setup_operation


def hue_evidence():
    result = filter_cel_evidence()
    result["adjustment"] = {
        "mode": "hsl-multiply",
        "hue": 0,
        "saturation": 0,
        "lightness": 10,
    }
    result["alpha"] = None
    return result


def hue_request(brightness_request):
    return HueSaturationRequest.model_validate(
        {
            **brightness_request.model_dump(
                exclude={
                    "brightness": True,
                    "contrast": True,
                    "application": {"tileset_mode"},
                }
            ),
            "adjustment": {
                "mode": "hsl-multiply",
                "hue": 0,
                "saturation": 0,
                "lightness": 10,
            },
        }
    )


def test_valid_hue_evidence_publishes_target(tmp_path):
    request, services, source, target, staged = setup_operation(
        tmp_path, hue_evidence()
    )
    result = hue_saturation(hue_request(request), services)
    assert result.operation == "spa filter hue-saturation"
    assert target.read_bytes() == b"native staged output"
    assert source.read_bytes() == b"original source"
    assert not staged[0].exists()


@pytest.mark.parametrize(
    "corruption",
    [
        "wrong_adjustment",
        "missing_adjustment",
        "wrong_alpha",
        "missing_cel_effect",
        "changed_flag",
        "deleted_cel_with_existing_image",
    ],
)
def test_mismatched_hue_evidence_cannot_publish(tmp_path, corruption):
    response = hue_evidence()
    if corruption == "wrong_adjustment":
        response["adjustment"]["mode"] = "hsl-add"
    elif corruption == "missing_adjustment":
        response["adjustment"] = None
    elif corruption == "wrong_alpha":
        response["alpha"] = 10
    elif corruption == "missing_cel_effect":
        response["cel_effects"] = []
    elif corruption == "deleted_cel_with_existing_image":
        response["cel_effects"][0]["after"] = None
    else:
        response["changed"] = False
    request, services, source, target, staged = setup_operation(tmp_path, response)
    with pytest.raises(RuntimeIssue) as caught:
        hue_saturation(hue_request(request), services)
    assert caught.value.kind == "response_malformed"
    assert_unpublished(source, target, staged)
