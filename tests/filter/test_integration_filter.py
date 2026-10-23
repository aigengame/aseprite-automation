"""Filter publication requires trustworthy evidence and cleans failed staging."""

import pytest

from spa.application.surface import info_result, schema_result
from spa.authoring.raster.filter import BrightnessContrastRequest, brightness_contrast
from spa.contracts.ports import RuntimeIssue
from spa.contracts.public import RuntimeRequest
from tests.filter.support import (
    assert_malformed,
    assert_unpublished,
    brightness_contrast_evidence,
    setup_brightness_contrast,
)
from tests.support import operation_services, runtime_observation

# The validator text that refuses each corrupted evidence field.
CONTRADICTION_CAUSES = {
    "missing_evidence": "images\n  Field required",
    "changed_flag": "Filter Image change disagrees with its content digests",
    "application": "Filter evidence disagrees with the requested application",
}
TILE_REFERENCE_CAUSES = {
    "missing_direct": "Tile references disagree with Filter Cel Image targets",
    "image_number": "Tile references disagree with Filter Cel Image targets",
    "duplicate": "Tile references disagree with Filter Cel Image targets",
    "empty_tile": "tile_index\n  Input should be greater than or equal to 1",
}


def test_valid_persisted_evidence_publishes_target(tmp_path):
    request, services, source, target, staged = setup_brightness_contrast(
        tmp_path, brightness_contrast_evidence()
    )
    result = brightness_contrast(request, services)
    assert result.target_commit.target_sprite_file == str(target)
    assert target.read_bytes() == b"native staged output"
    assert source.read_bytes() == b"original source"
    assert not staged[0].exists()


@pytest.mark.parametrize(
    "rejection, cause",
    [
        pytest.param({"code": "filter_invalid_target"}, "'message'", id="rejection0"),
        pytest.param(
            {"code": "filter_invalid_target", "message": "bad target", "details": {}},
            "reason\n  Field required",
            id="rejection1",
        ),
        pytest.param(
            {
                "code": "filter_invalid_target",
                "message": 1,
                "details": {"kind": "filter", "reason": "locked"},
            },
            "Invalid Filter rejection",
            id="rejection2",
        ),
    ],
)
def test_malformed_rejection_is_typed_and_does_not_publish(tmp_path, rejection, cause):
    request, services, source, target, staged = setup_brightness_contrast(
        tmp_path,
        {"rejection": rejection},
    )
    with pytest.raises(RuntimeIssue) as caught:
        brightness_contrast(request, services)
    assert_malformed(caught, cause)
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize("corruption", list(CONTRADICTION_CAUSES))
def test_contradictory_evidence_cannot_publish(tmp_path, corruption):
    response = brightness_contrast_evidence()
    if corruption == "missing_evidence":
        del response["images"]
    elif corruption == "changed_flag":
        response["images"][0]["changed"] = False
        response["changed"] = False
    else:
        response["application"] = "rgb-palette-colors"
    request, services, source, target, staged = setup_brightness_contrast(
        tmp_path, response
    )
    with pytest.raises(RuntimeIssue) as caught:
        brightness_contrast(request, services)
    assert_malformed(caught, CONTRADICTION_CAUSES[corruption])
    assert_unpublished(source, target, staged)


def test_kernel_exception_discards_stage_and_preserves_both_files(tmp_path):
    request, services, source, target, staged = setup_brightness_contrast(
        tmp_path, crash=True
    )
    with pytest.raises(RuntimeError, match="kernel interrupted after staging"):
        brightness_contrast(request, services)
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize("corruption", ["none", *TILE_REFERENCE_CAUSES])
def test_tile_reference_evidence_controls_publication(tmp_path, corruption):
    response = brightness_contrast_evidence()
    response["requested_tileset_mode"] = response["observed_tileset_mode"] = "manual"
    image = response["images"][0]
    image.update(image_kind="tilemap-placement", changed=False)
    image["after_content_digest"] = image["before_content_digest"]
    reference = {
        **response["existing_target_cels"][0],
        "relationships": ["shared-tile", "direct-target"],
    }
    response["changed_tiles"] = [
        {
            "tileset_index": 1,
            "tile_index": 1,
            "tile_key": None,
            "before_content_digest": {"value": "0000000000000001"},
            "after_content_digest": {"value": "0000000000000002"},
            "referencing_cels": [reference],
        }
    ]
    if corruption == "missing_direct":
        reference["relationships"] = ["shared-tile"]
    elif corruption == "image_number":
        reference["image_number"] = 99
    elif corruption == "duplicate":
        response["changed_tiles"][0]["referencing_cels"].append(reference.copy())
    elif corruption == "empty_tile":
        response["changed_tiles"][0]["tile_index"] = 0
    request, services, source, target, staged = setup_brightness_contrast(
        tmp_path, response
    )
    request = BrightnessContrastRequest.model_validate(
        {
            **request.model_dump(),
            "application": {
                **request.application.model_dump(),
                "tileset_mode": "manual",
            },
        }
    )
    if corruption == "none":
        assert brightness_contrast(request, services).changed
        assert target.read_bytes() == b"native staged output"
    else:
        with pytest.raises(RuntimeIssue) as caught:
            brightness_contrast(request, services)
        assert_malformed(caught, TILE_REFERENCE_CAUSES[corruption])
        assert_unpublished(source, target, staged)


@pytest.mark.parametrize(
    "capability,available,unavailable",
    [
        (
            "aseprite_filter_brightness_contrast",
            "spa filter brightness-contrast",
            "spa paint line",
        ),
        ("aseprite_paint_line", "spa paint line", "spa filter brightness-contrast"),
        (
            "aseprite_filter_hue_saturation",
            "spa filter hue-saturation",
            "spa filter brightness-contrast",
        ),
        (
            "aseprite_filter_brightness_contrast",
            "spa filter brightness-contrast",
            "spa filter hue-saturation",
        ),
    ],
)
def test_filter_and_paint_capability_gates_are_independent(
    capability, available, unavailable
):
    result = info_result(
        RuntimeRequest(),
        operation_services(
            lambda _: runtime_observation("aseprite_sprite_inspection", capability)
        ),
    )
    assert available in result.supported_capabilities
    assert unavailable not in result.supported_capabilities


@pytest.mark.parametrize("name", ["color-curve", "replace-color", "hue-saturation"])
@pytest.mark.parametrize("brightness_available", [False, True])
@pytest.mark.parametrize("operation_available", [False, True])
def test_pixel_filter_manifest_gap_is_independent_of_brightness(
    name, brightness_available, operation_available
):
    capabilities = [
        "aseprite_runtime_introspection",
        "aseprite_sprite_inspection",
    ]
    if operation_available:
        capabilities.append(f"aseprite_filter_{name.replace('-', '_')}")
    if brightness_available:
        capabilities.append("aseprite_filter_brightness_contrast")
    result = schema_result(
        RuntimeRequest(),
        operation_services(lambda _: runtime_observation(*capabilities)),
    )
    operations = {item.operation for item in result.operations}
    gaps = {item.capability for item in result.capability_gaps}

    assert (f"spa filter {name}" in operations) == operation_available
    assert (f"spa filter {name}: Tilemap pixels" in gaps) == operation_available
    assert (f"spa filter {name}" in gaps) != operation_available
    assert ("spa filter brightness-contrast" in operations) == brightness_available
    assert (
        "spa filter brightness-contrast: Manual Tilemap pixels" in gaps
    ) == brightness_available


@pytest.mark.parametrize("tilemap_available", [True, False])
def test_tilemap_gap_does_not_hide_ordinary_filter(tilemap_available):
    capabilities = [
        "aseprite_sprite_inspection",
        "aseprite_filter_brightness_contrast",
        "aseprite_filter_hue_saturation",
    ]
    if tilemap_available:
        capabilities.append("aseprite_filter_brightness_contrast_tilemap_manual")
    result = info_result(
        RuntimeRequest(),
        operation_services(lambda _: runtime_observation(*capabilities)),
    )
    assert "spa filter brightness-contrast" in result.supported_capabilities
    assert any(
        gap.capability == "spa filter hue-saturation: Tilemap pixels"
        for gap in result.capability_gaps
    )
    assert (
        any("Manual Tilemap" in gap.capability for gap in result.capability_gaps)
        != tilemap_available
    )
