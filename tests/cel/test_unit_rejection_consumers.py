"""Shared Cel rejection translation keeps each consumer's address and failure facts."""

import json
from pathlib import Path

import pytest

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import OPERATIONS
from spa.contracts.ports import KernelInvocationResult, OperationServices
from spa.contracts.public import Diagnostics, FailureEnvelope
from tests.support import runtime_observation

ADDRESS = {"layer": {"layer_path": [2, 1]}, "frame_number": 2}
DESTINATION = {"layer": {"layer_name": "destination"}, "frame_number": 3}
AREA = {"x": 0, "y": 0, "width": 1, "height": 1}
COLOR = {"kind": "rgba", "red": 30, "green": 40, "blue": 50, "alpha": 255}
SNAPSHOT = {
    "coordinate_space": "image-pixel",
    "color_mode": "rgb",
    "rectangle": AREA,
    "rows": [[{"length": 1, "color": COLOR}]],
}


@pytest.mark.parametrize(
    ("operation", "options", "role"),
    [
        ("cel clear", {"target": ADDRESS}, "target"),
        ("cel copy", {"source": ADDRESS, "destination": DESTINATION}, "source"),
        ("cel copy", {"source": ADDRESS, "destination": DESTINATION}, "destination"),
        (
            "motion apply",
            {
                "layer": ADDRESS["layer"],
                "from_frame": 2,
                "to_frame": 3,
                "opacity": {
                    "interpolation": "linear",
                    "rounding": "floor",
                    "keys": [
                        {"frame_number": 2, "opacity": 0},
                        {"frame_number": 3, "opacity": 255},
                    ],
                },
            },
            "target",
        ),
        (
            "image resize",
            {
                "target": ADDRESS,
                "width": 4,
                "height": 4,
                "method": "nearest-neighbor",
                "position_policy": {"kind": "keep"},
            },
            "target",
        ),
        (
            "image get",
            {"source": {"kind": "individual", "target": ADDRESS, "rectangle": AREA}},
            "target",
        ),
        (
            "paint composite",
            {
                "target": ADDRESS,
                "position": {"x": 0, "y": 0},
                "opacity": 255,
                "blend_mode": "normal",
                "input": {"kind": "inline", "snapshot": SNAPSHOT},
            },
            "target",
        ),
        (
            "paint line",
            {
                "target": ADDRESS,
                "coordinate_space": "image-pixel",
                "from": {"x": 0, "y": 0},
                "to": {"x": 0, "y": 0},
                "brush": {"kind": "circle", "size": 1},
                "color": COLOR,
                "ink": "simple",
                "opacity": 255,
            },
            "target",
        ),
    ],
)
@pytest.mark.parametrize(
    "code",
    ["layer_missing", "cel_frame_out_of_bounds", "cel_not_found", "unknown_rejection"],
)
def test_cel_rejection_through_each_feature_consumer(
    tmp_path: Path,
    operation: str,
    options: dict,
    role: str,
    code: str,
) -> None:
    descriptor = next(item for item in OPERATIONS if item.name == operation)
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    if operation == "image get":
        request = {"sprite_file": str(source), **options}
    else:
        request = {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            **options,
        }
    addressed = DESTINATION if role == "destination" else ADDRESS
    calls = []

    def invoke(_observation, handler, payload, _timeout):
        calls.append(handler.name)
        if "staged_sprite_file" in payload:
            Path(payload["staged_sprite_file"]).write_bytes(b"unverified")
        return KernelInvocationResult(
            {
                "rejection": {
                    "code": code,
                    "message": "native refusal",
                    "role": role,
                    "frame_number": addressed["frame_number"],
                }
            },
            "/response.json",
            Diagnostics(exit_status=0),
        )

    requirements = descriptor.runtime_requirements
    assert requirements is not None
    services = OperationServices(
        probe_runtime=lambda _request: runtime_observation(
            *requirements.required_capabilities
        ),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
    )
    outcome = dispatch(descriptor, json.dumps(request), {}, services, FAILURE_CODES)
    assert isinstance(outcome, FailureEnvelope)
    assert len(calls) == 1
    if code == "unknown_rejection":
        assert outcome.code == "kernel_response_invalid"
        assert outcome.category == "kernel_protocol"
    else:
        assert outcome.code == code
        assert outcome.category == "input"
        assert outcome.message == "native refusal"
        details = outcome.details.model_dump(exclude_none=True)
        if code == "layer_missing":
            assert details == {
                "kind": "layer_target",
                "address_role": role,
                "address": addressed["layer"],
            }
        elif code == "cel_frame_out_of_bounds":
            assert details == {
                "kind": "cel_frame_range",
                "from_frame": addressed["frame_number"],
                "to_frame": 3
                if operation == "motion apply"
                else addressed["frame_number"],
            }
        else:
            assert details == {"kind": "cel_target", "target": addressed}
    assert source.read_bytes() == b"source"
    assert target.read_bytes() == b"target"
    assert set(tmp_path.iterdir()) == {source, target}
