"""Static Paint Composite contract and failure containment before native execution."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.authoring.raster.paint_composite import (
    COMPOSITE_OPERATIONS,
    PaintCompositeRequest,
    composite_capability_gaps,
)
from spa.contracts.ports import KernelInvocationResult, OperationServices
from spa.contracts.public import Diagnostics, FailureEnvelope
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


@pytest.mark.parametrize("coordinate", [-(2**31) - 1, 2**31, 2**53 + 1])
@pytest.mark.parametrize("axis", ["x", "y"])
def test_composite_position_rejects_coordinates_outside_signed_32_bit(
    coordinate: int, axis: str
) -> None:
    position = {"x": 0, "y": 0, axis: coordinate}
    with pytest.raises(ValidationError):
        PaintCompositeRequest.model_validate({**_request(), "position": position})


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


def test_missing_indexed_capability_refuses_before_kernel(tmp_path: Path) -> None:
    request = _request()
    snapshot = request["input"]["snapshot"]
    snapshot["color_mode"] = "indexed"
    snapshot["rows"][0][0]["color"] = {"kind": "palette-index", "index": 1}
    request["palette_frame_number"] = 1
    request["source_sprite_file"] = str(tmp_path / "source.aseprite")
    request["target_sprite_file"] = str(tmp_path / "target.aseprite")
    observation = runtime_observation(
        "aseprite_paint_composite",
        "aseprite_sprite_inspection",
        "aseprite_cel_lifecycle",
    )

    def unexpected_invoke(*_args):
        raise AssertionError("unverified native capability must not be invoked")

    outcome = dispatch(
        COMPOSITE_OPERATIONS[0],
        json.dumps(request),
        {},
        OperationServices(
            probe_runtime=lambda _: observation,
            invoke_kernel=unexpected_invoke,
            target_files=LocalTargetFiles(),
        ),
        FAILURE_CODES,
    )
    assert isinstance(outcome, FailureEnvelope)
    assert outcome.code == "paint_composite_unsupported"
    assert (
        outcome.details.model_dump()["gap"]["capability"]
        == "spa paint composite: indexed"
    )
    assert any(
        gap.capability == "spa paint composite: indexed"
        for gap in composite_capability_gaps("test", observation.verified_capabilities)
    )
    assert not list(tmp_path.iterdir())
