"""Animation request validation and audit response checks without native execution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from spa.adapters.files import LocalTargetFiles
from spa.authoring.document.animation import (
    AnimationAuditRequest,
    AnimationCompareRequest,
    AnimationPreviewRequest,
    audit_animation,
)
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationServices,
    RuntimeIssue,
    RuntimeObservation,
)
from spa.contracts.public import Diagnostics


@pytest.mark.parametrize(
    "request_type", [AnimationCompareRequest, AnimationPreviewRequest]
)
def test_frame_pair_requires_distinct_frames(request_type) -> None:
    fields = {"earlier_frame": 1, "later_frame": 1}
    if request_type is AnimationCompareRequest:
        fields["sprite_file"] = "source.aseprite"
    else:
        fields["source_sprite_file"] = "source.aseprite"
        fields["destination"] = {"path": "preview.png", "if_exists": "fail"}
    with pytest.raises(ValidationError, match="must precede"):
        request_type.model_validate(fields)


def test_audit_limits_are_discoverable_in_request_schema() -> None:
    assert AnimationAuditRequest.model_json_schema()["x-spa-audit-limits"] == {
        "coverage_observations": 1024,
        "overlap_pixel_checks": 16_777_216,
    }


@pytest.mark.parametrize("coverage", ["required_cels", "durations", "overlaps"])
def test_audit_rejects_duplicate_coverage_with_omitted_frame(
    tmp_path: Path, coverage: str
) -> None:
    request_data: dict[str, object] = {
        "sprite_file": str(tmp_path / "source.aseprite"),
        "from_frame": 1,
        "to_frame": 2,
    }
    result: dict[str, object] = {
        "complete": True,
        "scope": {"from_frame": 1, "to_frame": 2},
        "required_cels": [],
        "durations": [],
        "overlaps": [],
        "findings": [],
    }
    if coverage == "required_cels":
        request_data["required_cels"] = [
            {"layer": {"layer_path": [1]}, "frame_number": number} for number in (1, 2)
        ]
        result["required_cels"] = [
            {"layer_path": [1], "frame_number": 1, "exists": True}
        ] * 2
    elif coverage == "durations":
        request_data["duration_bounds"] = {"minimum_ms": 1, "maximum_ms": 500}
        result["durations"] = [{"frame_number": 1, "duration_ms": 100}] * 2
    else:
        request_data["non_overlap"] = [
            {"first_layer": {"layer_path": [1]}, "second_layer": {"layer_path": [2]}}
        ]
        result["overlaps"] = [
            {
                "first_layer_path": [1],
                "second_layer_path": [2],
                "frame_number": 1,
                "overlap_pixels": 0,
            }
        ] * 2

    def invoke(_observation, _handler, _payload, _timeout):
        return KernelInvocationResult(
            payload=result,
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    observation = RuntimeObservation(
        selection_source="explicit",
        requested_path="/aseprite",
        discovered_path="/aseprite",
        canonical_path="/aseprite",
        resource_path="/data/gui.xml",
        aseprite_version="test",
        api_version=41,
        lua_version="Lua 5.4",
        verified_prerequisites=("aseprite_scripting", "lua_file_io", "aseprite_json"),
        verified_capabilities=("aseprite_sprite_inspection", "aseprite_cel_lifecycle"),
    )
    services = OperationServices(
        probe_runtime=lambda _request: observation,
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
    )
    request = AnimationAuditRequest.model_validate(request_data)
    with pytest.raises(RuntimeIssue) as failure:
        audit_animation(request, services)
    assert failure.value.kind == "response_malformed"
