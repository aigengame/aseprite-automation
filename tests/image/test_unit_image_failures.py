"""Image mutations reject malformed private Kernel failures before publication."""

import json
from pathlib import Path

import pytest

from spa.application import dispatch
from spa.contracts import Diagnostics, FailureEnvelope
from spa.failure_registry import FAILURE_CODES
from spa.image import IMAGE_OPERATIONS
from spa.ports import (
    KernelInvocationResult,
    OperationServices,
    RuntimeObservation,
    TargetCommitObservation,
)


class _TargetFiles:
    def __init__(self) -> None:
        self.commits = 0
        self.discards = 0

    def same_publication_entry(self, _source: Path, _target: Path) -> bool:
        return False

    def same_publication_target(self, _source: Path, _target: Path) -> bool:
        return False

    def staged_path(self, target: Path) -> Path:
        return target.with_suffix(".staged.aseprite")

    def commit(
        self, _staged: Path, _target: Path, *, overwrite: bool
    ) -> TargetCommitObservation:
        self.commits += 1
        raise AssertionError("malformed Kernel output must not be published")

    def discard(self, _staged: Path) -> None:
        self.discards += 1


@pytest.mark.parametrize(
    ("operation", "options", "rejection"),
    [
        (
            "image resize",
            {"width": 4, "height": 4, "method": "nearest-neighbor"},
            {"code": [], "message": "malformed code"},
        ),
        (
            "image rotate",
            {"angle": 90},
            {"code": "image_rotate_position_out_of_bounds", "message": "missing facts"},
        ),
        (
            "image rotate",
            {"angle": 90},
            {
                "code": "image_rotate_position_out_of_bounds",
                "message": "incomplete facts",
                "details": {
                    "coordinate_space": "canvas-pixel",
                    "attempted_position": {"x": -32774, "y": 32767},
                    "allowed_minimum": -32768,
                },
            },
        ),
    ],
)
def test_malformed_rejection_uses_failure_envelope(
    operation: str,
    options: dict,
    rejection: dict,
) -> None:
    files = _TargetFiles()
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
        verified_capabilities=(
            "aseprite_image_resize",
            "aseprite_image_rotate",
            "aseprite_cel_lifecycle",
            "aseprite_cel_relationships",
            "aseprite_sprite_inspection",
        ),
    )
    invocation = KernelInvocationResult(
        payload={"rejection": rejection},
        response_path="/response.json",
        diagnostics=Diagnostics(exit_status=0),
    )
    services = OperationServices(
        probe_runtime=lambda _request: observation,
        invoke_kernel=lambda *_args: invocation,
        target_files=files,
    )
    request = {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "position_policy": {"kind": "keep"},
        "aseprite": "/aseprite",
        **options,
    }

    outcome = dispatch(
        next(item for item in IMAGE_OPERATIONS if item.name == operation),
        json.dumps(request),
        {},
        services,
        FAILURE_CODES,
    )

    assert isinstance(outcome, FailureEnvelope)
    assert outcome.code == "kernel_response_invalid"
    assert files.commits == 0
    assert files.discards == 1
