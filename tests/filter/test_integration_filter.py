"""Filter publication requires trustworthy evidence and cleans failed staging."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from spa.adapters.files import LocalTargetFiles
from spa.authoring.raster.filter import BrightnessContrastRequest, brightness_contrast
from spa.contracts.ports import KernelInvocationResult, RuntimeIssue
from spa.contracts.public import Diagnostics
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
                "before_content_digest": {"value": "0000000000000001"},
                "after_content_digest": {"value": "0000000000000002"},
                "changed": True,
            }
        ],
        "processed_image_numbers": [1],
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
