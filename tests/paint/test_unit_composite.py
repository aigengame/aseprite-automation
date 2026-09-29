"""Static Paint Composite contract and failure containment before native execution."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from spa.application import dispatch
from spa.contracts import Diagnostics, FailureEnvelope
from spa.failure_registry import FAILURE_CODES
from spa.file_adapter import LocalArtifactFiles, LocalTargetFiles
from spa.paint_composite import COMPOSITE_OPERATIONS, PaintCompositeRequest
from spa.ports import KernelInvocationResult, OperationServices
from tests.support import runtime_observation


def _request() -> dict:
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "position": {"x": 0, "y": 0},
        "opacity": 255,
        "blend_mode": "normal",
        "input": {
            "kind": "inline",
            "snapshot": {
                "coordinate_space": "image-pixel",
                "color_mode": "rgb",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                "rows": [
                    [
                        {
                            "length": 1,
                            "color": {
                                "kind": "rgba",
                                "red": 1,
                                "green": 2,
                                "blue": 3,
                                "alpha": 128,
                            },
                        }
                    ]
                ],
            },
        },
    }


@pytest.mark.parametrize("opacity", [-1, 256, 0.5, True, "255"])
def test_composite_opacity_must_be_an_integer_byte(opacity: object) -> None:
    with pytest.raises(ValidationError):
        PaintCompositeRequest.model_validate({**_request(), "opacity": opacity})


@pytest.mark.parametrize(
    "mode", ["src", "dst", "merge", "neg-bw", "addition-n", "normal-n"]
)
def test_internal_or_unknown_blend_modes_are_not_exposed(mode: str) -> None:
    with pytest.raises(ValidationError):
        PaintCompositeRequest.model_validate({**_request(), "blend_mode": mode})


@pytest.mark.parametrize(
    "response", [{}, {"rejection": {"code": [], "message": "bad"}}]
)
def test_malformed_kernel_result_does_not_replace_existing_target(
    tmp_path: Path,
    response: dict,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"source")
    target.write_bytes(b"target")

    def invoke(_observation, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"unverified stage")
        return KernelInvocationResult(
            payload=response,
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    services = OperationServices(
        probe_runtime=lambda _: runtime_observation(
            "aseprite_paint_composite",
            "aseprite_sprite_inspection",
            "aseprite_cel_lifecycle",
        ),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
    )
    outcome = dispatch(
        COMPOSITE_OPERATIONS[0],
        json.dumps(
            {
                **_request(),
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": True,
            }
        ),
        {},
        services,
        FAILURE_CODES,
    )
    assert isinstance(outcome, FailureEnvelope)
    assert outcome.code in {"kernel_response_invalid", "response_malformed"}
    assert target.read_bytes() == b"target"
    assert source.read_bytes() == b"source"
    assert {item.name for item in tmp_path.iterdir()} == {
        "source.aseprite",
        "target.aseprite",
    }
