"""Despeckle evidence and capability gates protect Target Commit."""

import pytest

from spa.application.surface import schema_result
from spa.authoring.raster.despeckle import DespeckleRequest, despeckle
from spa.contracts.ports import RuntimeIssue
from spa.contracts.public import RuntimeRequest
from tests.filter.support import (
    assert_unpublished,
    filter_cel_evidence,
    setup_filter_staging,
)
from tests.support import operation_services, runtime_observation


def request_for(source, target):
    return DespeckleRequest(
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        width=3,
        height=1,
        tiled_mode="none",
        pixels={
            "color_mode": "rgb",
            "channels": {"kind": "components", "names": ["red"]},
            "cels_target": {"kind": "all"},
        },
    )


def response_for():
    response = filter_cel_evidence()
    response.update(
        width=3, height=1, tiled_mode="none", anchor={"x": 1, "y": 0}, sample_count=3
    )
    return response


def test_matched_native_observations_publish(tmp_path):
    services, source, target, staged = setup_filter_staging(tmp_path, response_for())
    result = despeckle(request_for(source, target), services)
    assert result.persisted_reopen_verified
    assert target.read_bytes() == b"native staged output"
    assert source.read_bytes() == b"original source"
    assert not staged[0].exists()


def test_omitted_selection_cannot_publish_empty_selection_evidence(tmp_path):
    response = response_for()
    response["selection"] = {"kind": "empty"}
    services, source, target, staged = setup_filter_staging(tmp_path, response)
    with pytest.raises(RuntimeIssue) as caught:
        despeckle(request_for(source, target), services)
    assert caught.value.kind == "response_malformed"
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize(
    "layers, frames",
    [
        ([{"layer_path": [1]}], [2]),
        ([{"layer_path": [2]}], [1]),
        ([{"layer_path": [1]}], [1, 2]),
        ([{"layer_path": [1]}, {"layer_path": [2]}], [1]),
        ([{"layer_name": "Ink"}], [2]),
        ([{"layer_uuid": "persisted-layer"}], [2]),
    ],
    ids=["frame", "path", "missing-frame", "missing-layer", "name-frame", "uuid-frame"],
)
def test_selected_targets_cannot_publish_different_intersections(
    tmp_path, layers, frames
):
    response = response_for()
    response["cels_target_kind"] = "selected"
    services, source, target, staged = setup_filter_staging(tmp_path, response)
    data = request_for(source, target).model_dump()
    data["pixels"]["cels_target"] = {
        "kind": "selected",
        "layers": layers,
        "frame_numbers": frames,
    }
    with pytest.raises(RuntimeIssue) as caught:
        despeckle(DespeckleRequest.model_validate(data), services)
    assert caught.value.kind == "response_malformed"
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize(
    "layer",
    [{"layer_path": [1]}, {"layer_name": "Ink"}, {"layer_uuid": "persisted-layer"}],
)
def test_resolved_layer_addresses_can_publish_matching_frames(tmp_path, layer):
    response = response_for()
    response["cels_target_kind"] = "selected"
    services, source, target, staged = setup_filter_staging(tmp_path, response)
    data = request_for(source, target).model_dump()
    data["pixels"]["cels_target"] = {
        "kind": "selected",
        "layers": [layer],
        "frame_numbers": [1],
    }
    result = despeckle(DespeckleRequest.model_validate(data), services)
    assert result.requested_intersections[0].layer_path == [1]
    assert target.read_bytes() == b"native staged output"
    assert source.read_bytes() == b"original source"
    assert not staged[0].exists()


def test_existing_targets_must_agree_with_reported_intersections(tmp_path):
    response = response_for()
    response["cels_target_kind"] = "selected"
    response["requested_intersections"] = [
        {"layer_path": [1], "frame_number": 2, "image_number": 1}
    ]
    services, source, target, staged = setup_filter_staging(tmp_path, response)
    data = request_for(source, target).model_dump()
    data["pixels"]["cels_target"] = {
        "kind": "selected",
        "layers": [{"layer_path": [1]}],
        "frame_numbers": [2],
    }
    with pytest.raises(RuntimeIssue) as caught:
        despeckle(DespeckleRequest.model_validate(data), services)
    assert caught.value.kind == "response_malformed"
    assert_unpublished(source, target, staged)


def test_empty_selection_cannot_publish_nonempty_selection_evidence(tmp_path):
    services, source, target, staged = setup_filter_staging(tmp_path, response_for())
    data = request_for(source, target).model_dump()
    data["pixels"]["selection"] = {"kind": "empty"}
    with pytest.raises(RuntimeIssue) as caught:
        despeckle(DespeckleRequest.model_validate(data), services)
    assert caught.value.kind == "response_malformed"
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize(
    "requested, observed",
    [
        (
            {"kind": "all", "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1}},
            {"kind": "empty"},
        ),
        (
            {
                "kind": "mask",
                "bounds": {"x": 0, "y": 0, "width": 3, "height": 1},
                "rows": [
                    {"y": 0, "runs": [{"x": 0, "length": 1}, {"x": 2, "length": 1}]}
                ],
            },
            {"kind": "all", "rectangle": {"x": 0, "y": 0, "width": 3, "height": 1}},
        ),
        (
            {"kind": "all", "rectangle": {"x": 0, "y": 0, "width": 3, "height": 1}},
            {
                "kind": "mask",
                "bounds": {"x": 0, "y": 0, "width": 3, "height": 1},
                "rows": [
                    {"y": 0, "runs": [{"x": 0, "length": 1}, {"x": 2, "length": 1}]}
                ],
            },
        ),
        (
            {"kind": "all", "rectangle": {"x": -1, "y": 0, "width": 3, "height": 1}},
            {"kind": "all", "rectangle": {"x": -1, "y": 0, "width": 1, "height": 1}},
        ),
        (
            {"kind": "all", "rectangle": {"x": 1, "y": 0, "width": 1, "height": 1}},
            {"kind": "all", "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1}},
        ),
        (
            {
                "kind": "mask",
                "bounds": {"x": 1, "y": 0, "width": 1, "height": 1},
                "rows": [{"y": 0, "runs": [{"x": 1, "length": 1}]}],
            },
            {"kind": "all", "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1}},
        ),
    ],
    ids=[
        "lost-origin",
        "filled-mask-hole",
        "rectangle-became-mask",
        "off-canvas",
        "expanded-rectangle",
        "expanded-mask",
    ],
)
def test_impossible_selection_observations_cannot_publish(
    tmp_path, requested, observed
):
    response = response_for()
    response["selection"] = observed
    services, source, target, staged = setup_filter_staging(tmp_path, response)
    data = request_for(source, target).model_dump()
    data["pixels"]["selection"] = requested
    with pytest.raises(RuntimeIssue) as caught:
        despeckle(DespeckleRequest.model_validate(data), services)
    assert caught.value.kind == "response_malformed"
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize(
    "corruption",
    [
        "width",
        "height",
        "tiled_mode",
        "anchor",
        "sample_count",
        "channels",
        "processed_image_numbers",
        "cel_effects",
        "palette_after",
        "persisted_reopen_verified",
    ],
)
def test_inconsistent_native_evidence_cannot_publish(tmp_path, corruption):
    response = response_for()
    invalid = {
        "width": 4,
        "height": 2,
        "tiled_mode": "both",
        "anchor": {"x": 0, "y": 0},
        "sample_count": 1,
        "channels": {"kind": "index"},
        "processed_image_numbers": [],
        "cel_effects": [],
        "palette_after": {},
        "persisted_reopen_verified": False,
    }
    response[corruption] = invalid[corruption]
    services, source, target, staged = setup_filter_staging(tmp_path, response)
    with pytest.raises(RuntimeIssue) as caught:
        despeckle(request_for(source, target), services)
    assert caught.value.kind == "response_malformed"
    assert_unpublished(source, target, staged)


def test_interrupted_kernel_discards_staging(tmp_path):
    services, source, target, staged = setup_filter_staging(tmp_path, crash=True)
    with pytest.raises(RuntimeError, match="kernel interrupted"):
        despeckle(request_for(source, target), services)
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize("supported", [False, True])
def test_schema_gates_despeckle_and_never_publishes_convolution(supported):
    capabilities = ["aseprite_sprite_inspection"]
    if supported:
        capabilities.append("aseprite_filter_despeckle")
    result = schema_result(
        RuntimeRequest(),
        operation_services(lambda _: runtime_observation(*capabilities)),
    )
    names = [descriptor.operation for descriptor in result.operations]
    assert ("spa filter despeckle" in names) is supported
    assert "spa filter convolution-matrix" not in names
    assert any(
        gap.capability == "spa filter convolution-matrix"
        for gap in result.capability_gaps
    )
    if supported:
        descriptor = next(
            descriptor
            for descriptor in result.operations
            if descriptor.operation == "spa filter despeckle"
        )
        assert "application" not in descriptor.request_schema["properties"]
        assert any("without Green" in gap.capability for gap in result.capability_gaps)
