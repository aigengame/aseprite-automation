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
