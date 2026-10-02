"""Filter publication requires trustworthy evidence and cleans failed staging."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from spa.adapters.files import LocalTargetFiles
from spa.application.surface import info_result, schema_result
from spa.authoring.raster.filter import BrightnessContrastRequest, brightness_contrast
from spa.contracts.ports import KernelInvocationResult, RuntimeIssue
from spa.contracts.public import Diagnostics, RuntimeRequest
from tests.support import operation_services, runtime_observation


def evidence():
    palette = {
        "frame_count": 1,
        "palette_changes": [
            {
                "palette_frame_number": 1,
                "effective_frame_range": {"from_frame": 1, "to_frame": 1},
                "entries": [
                    {"index": 0, "color": {"red": 0, "green": 0, "blue": 0, "alpha": 0}}
                ],
            }
        ],
    }
    cel = {"layer_path": [1], "frame_number": 1, "image_number": 1}
    return {
        "brightness": 10,
        "contrast": 0,
        "application": "pixels",
        "cels_target_kind": "all",
        "selection": {
            "kind": "all",
            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
        },
        "color_mode": "rgb",
        "palette_basis": None,
        "palette_indexes": [],
        "palette_before": palette,
        "palette_after": deepcopy(palette),
        "channels": {"kind": "components", "names": ["red"]},
        "requested_intersections": [cel],
        "existing_target_cels": [cel],
        "excluded_layers": [],
        "images": [
            {
                "image_number": 1,
                "image_kind": "ordinary",
                "before_content_digest": {"value": "0000000000000001"},
                "after_content_digest": {"value": "0000000000000002"},
                "changed": True,
            }
        ],
        "processed_image_numbers": [1],
        "requested_tileset_mode": None,
        "observed_tileset_mode": None,
        "changed_tiles": [],
        "affected_cels": [cel],
        "changed": True,
        "persisted_reopen_verified": True,
    }


def setup_operation(tmp_path, response=None, crash=False):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"original source")
    target.write_bytes(b"preexisting target")
    request = BrightnessContrastRequest.model_validate(
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            "brightness": 10,
            "contrast": 0,
            "application": {
                "kind": "pixels",
                "color_mode": "rgb",
                "channels": {"kind": "components", "names": ["red"]},
                "cels_target": {"kind": "all"},
            },
        }
    )
    staged = []

    def invoke(_observation, _handler, payload, _timeout):
        stage = Path(payload["staged_sprite_file"])
        stage.write_bytes(b"native staged output")
        staged.append(stage)
        if crash:
            raise RuntimeError("kernel interrupted after staging")
        return KernelInvocationResult(
            payload=response,
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    services = replace(
        operation_services(lambda _: runtime_observation()),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
    )
    return request, services, source, target, staged


def assert_unpublished(source, target, staged):
    assert source.read_bytes() == b"original source"
    assert target.read_bytes() == b"preexisting target"
    assert len(staged) == 1
    assert not staged[0].exists()


def test_valid_persisted_evidence_publishes_target(tmp_path):
    request, services, source, target, staged = setup_operation(tmp_path, evidence())
    result = brightness_contrast(request, services)
    assert result.target_commit.target_sprite_file == str(target)
    assert target.read_bytes() == b"native staged output"
    assert source.read_bytes() == b"original source"
    assert not staged[0].exists()


@pytest.mark.parametrize(
    "rejection",
    [
        {"code": "filter_invalid_target"},
        {"code": "filter_invalid_target", "message": "bad target", "details": {}},
        {
            "code": "filter_invalid_target",
            "message": 1,
            "details": {"kind": "filter", "reason": "locked"},
        },
    ],
)
def test_malformed_rejection_is_typed_and_does_not_publish(tmp_path, rejection):
    request, services, source, target, staged = setup_operation(
        tmp_path,
        {"rejection": rejection},
    )
    with pytest.raises(RuntimeIssue) as caught:
        brightness_contrast(request, services)
    assert caught.value.kind == "response_malformed"
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize(
    "corruption", ["missing_evidence", "changed_flag", "application"]
)
def test_contradictory_evidence_cannot_publish(tmp_path, corruption):
    response = evidence()
    if corruption == "missing_evidence":
        del response["images"]
    elif corruption == "changed_flag":
        response["images"][0]["changed"] = False
        response["changed"] = False
    else:
        response["application"] = "rgb-palette-colors"
    request, services, source, target, staged = setup_operation(tmp_path, response)
    with pytest.raises(RuntimeIssue) as caught:
        brightness_contrast(request, services)
    assert caught.value.kind == "response_malformed"
    assert_unpublished(source, target, staged)


def test_kernel_exception_discards_stage_and_preserves_both_files(tmp_path):
    request, services, source, target, staged = setup_operation(tmp_path, crash=True)
    with pytest.raises(RuntimeError, match="kernel interrupted after staging"):
        brightness_contrast(request, services)
    assert_unpublished(source, target, staged)


@pytest.mark.parametrize(
    "corruption", ["none", "missing_direct", "image_number", "duplicate", "empty_tile"]
)
def test_tile_reference_evidence_controls_publication(tmp_path, corruption):
    response = evidence()
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
    request, services, source, target, staged = setup_operation(tmp_path, response)
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
        assert caught.value.kind == "response_malformed"
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
