"""No fixed-pixel Filter publishes inconsistent native observations."""

import pytest

from spa.authoring.raster.color_curve import ColorCurveRequest, color_curve
from spa.authoring.raster.replace_color import ReplaceColorRequest, replace_color
from spa.contracts.ports import RuntimeIssue
from tests.filter.test_integration_filter import assert_unpublished, setup_operation
from tests.filter.test_integration_hue_saturation import hue_evidence


def operation_case(name):
    response = hue_evidence()
    for field in ("application", "palette_indexes", "adjustment", "alpha"):
        del response[field]
    if name == "color-curve":
        parameters = {"points": [{"input": 0, "output": 255}]}
        request_type, execute = ColorCurveRequest, color_curve
    else:
        parameters = {
            "from": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 255},
            "to": {"kind": "rgba", "red": 255, "green": 255, "blue": 255, "alpha": 255},
            "tolerance": 0,
        }
        response["changed_pixel_count"] = 1
        request_type, execute = ReplaceColorRequest, replace_color
    response.update(parameters)
    return response, parameters, request_type, execute


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
@pytest.mark.parametrize(
    "corruption",
    [
        None,
        "channels",
        "palette",
        "cel_survival",
        "processing",
        "parameters",
        "persisted",
    ],
)
def test_pixel_filter_commit_requires_consistent_evidence(tmp_path, name, corruption):
    response, parameters, request_type, execute = operation_case(name)
    if corruption == "channels":
        response["channels"] = {"kind": "components", "names": ["alpha"]}
    elif corruption == "palette":
        response["palette_after"]["frame_count"] += 1
    elif corruption == "cel_survival":
        response["cel_effects"][0]["after"] = None
    elif corruption == "processing":
        response["processed_image_numbers"] = []
    elif corruption == "parameters":
        response["points" if name == "color-curve" else "tolerance"] = (
            [] if name == "color-curve" else 1
        )
    elif corruption == "persisted":
        response["persisted_reopen_verified"] = False
    brightness, services, source, target, staged = setup_operation(tmp_path, response)
    fields = brightness.model_dump(exclude={"application", "brightness", "contrast"})
    application = brightness.application.model_dump(
        exclude={"kind", "tileset_mode"}, exclude_none=True
    )
    request = request_type.model_validate({**fields, **application, **parameters})
    if corruption:
        with pytest.raises(RuntimeIssue):
            execute(request, services)
        assert_unpublished(source, target, staged)
    else:
        execute(request, services)
        assert target.read_bytes() == b"native staged output"
        assert source.read_bytes() == b"original source"


def test_impossible_changed_count_cannot_publish(tmp_path):
    response, parameters, request_type, execute = operation_case("replace-color")
    response["changed_pixel_count"] = 2
    brightness, services, source, target, staged = setup_operation(tmp_path, response)
    request = request_type.model_validate(
        {
            **brightness.model_dump(exclude={"application", "brightness", "contrast"}),
            **brightness.application.model_dump(
                exclude={"kind", "tileset_mode"}, exclude_none=True
            ),
            **parameters,
        }
    )
    with pytest.raises(RuntimeIssue):
        execute(request, services)
    assert_unpublished(source, target, staged)
