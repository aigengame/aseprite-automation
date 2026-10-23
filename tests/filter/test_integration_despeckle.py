"""Despeckle evidence and capability gates protect Target Commit."""

import pytest

from spa.application.surface import schema_result
from spa.authoring.raster.despeckle import DespeckleRequest, despeckle
from spa.contracts.ports import RuntimeIssue
from spa.contracts.public import RuntimeRequest
from tests.filter.support import (
    assert_malformed,
    assert_unpublished,
    despeckle_evidence,
    setup_filter_staging,
)

# The validator text that refuses each corrupted evidence field.
NATIVE_PATH = "Despeckle observations disagree with its native pixel path"
EVIDENCE_CAUSES = {
    "width": NATIVE_PATH,
    "height": NATIVE_PATH,
    "anchor": NATIVE_PATH,
    "sample_count": NATIVE_PATH,
    "channels": "Filter evidence disagrees with the requested application",
    "processed_image_numbers": NATIVE_PATH,
    "cel_effects": "Cel effects must cover every affected Cel",
    "palette_after": "palette_after.frame_count\n  Field required",
    "persisted_reopen_verified": "persisted_reopen_verified\n  Input should be True",
}
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


def test_matched_native_observations_publish(tmp_path):
    services, source, target, staged = setup_filter_staging(
        tmp_path, despeckle_evidence()
    )
    result = despeckle(request_for(source, target), services)
    assert result.persisted_reopen_verified
    assert target.read_bytes() == b"native staged output"
    assert source.read_bytes() == b"original source"
    assert not staged[0].exists()


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
    response = despeckle_evidence()
    response["selection"] = observed
    services, source, target, staged = setup_filter_staging(tmp_path, response)
    data = request_for(source, target).model_dump()
    data["pixels"]["selection"] = requested
    with pytest.raises(RuntimeIssue) as caught:
        despeckle(DespeckleRequest.model_validate(data), services)
    assert_malformed(caught, "Filter evidence disagrees with the requested application")
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize("corruption", list(EVIDENCE_CAUSES))
def test_inconsistent_native_evidence_cannot_publish(tmp_path, corruption):
    response = despeckle_evidence()
    invalid = {
        "width": 4,
        "height": 2,
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
    assert_malformed(caught, EVIDENCE_CAUSES[corruption])
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
