"""Filter publication requires evidence for the requested targets and Selection."""

from copy import deepcopy

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
    "layer",
    [{"layer_path": [1]}, {"layer_name": "Ink"}, {"layer_uuid": "persisted-layer"}],
)
def test_resolved_targets_preserve_empty_intersections_and_linked_effects(
    tmp_path, filter_case, layer
):
    response, request_for, execute = filter_case
    response["cels_target_kind"] = "selected"
    response["requested_intersections"].append(
        {"layer_path": [1], "frame_number": 2, "image_number": None}
    )
    linked = {"layer_path": [1], "frame_number": 3, "image_number": 1}
    response["affected_cels"].append(linked)
    if "cel_effects" in response:
        response["cel_effects"].append({**response["cel_effects"][0], **linked})
    for key in ("palette_before", "palette_after"):
        response[key]["frame_count"] = 3
        response[key]["palette_changes"][0]["effective_frame_range"]["to_frame"] = 3
    services, source, target, staged = setup_filter_staging(tmp_path, response)

    result = execute(
        request_for(
            source,
            target,
            cels_target={
                "kind": "selected",
                "layers": [layer],
                "frame_numbers": [2, 1],
            },
        ),
        services,
    )

    assert result.requested_intersections[1].image_number is None
    assert result.affected_cels[-1].frame_number == 3
    assert target.read_bytes() == b"native staged output"
    assert source.read_bytes() == b"original source"
    assert not staged[0].exists()


@pytest.mark.parametrize(
    "requested, observed",
    [
        (None, {"kind": "all", "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1}}),
        ({"kind": "empty"}, {"kind": "empty"}),
        (
            {"kind": "all", "rectangle": {"x": -1, "y": -1, "width": 3, "height": 3}},
            {"kind": "all", "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1}},
        ),
        (
            {
                "kind": "mask",
                "bounds": {"x": -1, "y": 0, "width": 3, "height": 2},
                "rows": [
                    {"y": 0, "runs": [{"x": -1, "length": 3}]},
                    {"y": 1, "runs": [{"x": 0, "length": 1}]},
                ],
            },
            {"kind": "all", "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1}},
        ),
    ],
    ids=["unrestricted", "empty", "clipped-rectangle", "clipped-mask-normalized"],
)
def test_feasible_native_selection_can_publish(
    tmp_path, filter_case, requested, observed
):
    response, request_for, execute = filter_case
    response["selection"] = observed
    if observed["kind"] == "empty":
        response["changed"] = False
        for image in response["images"]:
            image["after_content_digest"] = deepcopy(image["before_content_digest"])
            image["changed"] = False
        if "changed_pixel_count" in response:
            response["changed_pixel_count"] = 0
    services, source, target, staged = setup_filter_staging(tmp_path, response)

    result = execute(request_for(source, target, selection=requested), services)

    assert result.selection.model_dump() == observed
    assert target.read_bytes() == b"native staged output"
    assert source.read_bytes() == b"original source"
    assert not staged[0].exists()


@pytest.mark.parametrize(
    "request_type, execute, response_factory, parameters",
    [
        (
            BrightnessContrastRequest,
            brightness_contrast,
            evidence,
            {"brightness": 10, "contrast": 0},
        ),
        (
            HueSaturationRequest,
            hue_saturation,
            hue_evidence,
            {
                "adjustment": {
                    "mode": "hsl-multiply",
                    "hue": 0,
                    "saturation": 0,
                    "lightness": 10,
                }
            },
        ),
    ],
    ids=["brightness-contrast", "hue-saturation"],
)
def test_palette_only_can_publish_without_pixel_target_evidence(
    tmp_path, request_type, execute, response_factory, parameters
):
    response = response_factory()
    response.update(
        application="indexed-palette-entries",
        color_mode="indexed",
        cels_target_kind=None,
        selection=None,
        palette_indexes=[0],
        palette_basis={"frame_number": 1, "palette_frame_number": 1, "palette_size": 1},
    )
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
    response["palette_after"]["palette_changes"][0]["entries"][0]["color"]["red"] = 80
    services, source, target, staged = setup_filter_staging(tmp_path, response)
    request = request_type.model_validate(
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            **parameters,
            "application": {
                "kind": "indexed-palette-entries",
                "palette_frame_number": 1,
                "entries": {"kind": "all"},
                "channels": {"kind": "components", "names": ["red"]},
            },
        }
    )

    result = execute(request, services)

    assert result.cels_target_kind is None
    assert result.selection is None
    assert result.images == []
    assert target.read_bytes() == b"native staged output"
    assert source.read_bytes() == b"original source"
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
