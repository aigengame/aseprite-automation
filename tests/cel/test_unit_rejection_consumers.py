"""Cel rejection translation keeps each consumer's address and failure facts.

These are the R5 rows of the Plan rule table. Each module that calls
`raise_cel_rejection` has rows, and a guard compares those modules with CALLERS. A
Plan and standalone `paint apply` translate a Cel rejection in their own code; the
Plan rows compare the Plan failure with the standalone failure.
"""

import ast
import json
from pathlib import Path

import pytest
from PIL import Image

import spa
from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png_input import decode_png_input
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.application.plan import ELIGIBLE_OPERATIONS
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


FEATURE_ROWS = [
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
]
MOTION = {
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
}
PAINT = {
    "target": {"layer_path": [2, 1], "frame_number": 2},
    "patch": {
        "coordinate_space": "image-pixel",
        "rectangle": AREA,
        "runs": [{"x": 0, "y": 0, "length": 1, "color": COLOR}],
    },
}
# Document consumers: (operation, options, address role, Cel target code).
DOCUMENT_ROWS = [
    ("cel add", {"target": ADDRESS}, "target", "cel_already_exists"),
    ("cel set", {"target": ADDRESS, "opacity": 0}, "target", "cel_not_found"),
    ("cel remove", {"target": ADDRESS}, "target", "cel_not_found"),
    (
        "cel link",
        {"source": ADDRESS, "destination": DESTINATION},
        "source",
        "cel_not_found",
    ),
    (
        "cel link",
        {"source": ADDRESS, "destination": DESTINATION},
        "destination",
        "cel_already_exists",
    ),
    ("cel unlink", {"target": ADDRESS}, "target", "cel_not_found"),
    (
        "image import",
        {"target": ADDRESS, "position": {"x": 0, "y": 0}},
        "target",
        "cel_already_exists",
    ),
]
# Each module that calls `raise_cel_rejection`, and the Operations of the rows above
# that reach that call.
CALLERS = {
    "spa.authoring.document.cel": {"cel clear", "cel add", "cel remove"},
    "spa.authoring.document.cel_relationship": {
        "cel copy",
        "cel set",
        "cel link",
        "cel unlink",
    },
    "spa.authoring.document.motion": {"motion apply"},
    "spa.authoring.raster.image": {"image resize"},
    "spa.authoring.raster.image_import": {"image import"},
    "spa.authoring.raster.image_snapshot": {"image get"},
    "spa.authoring.raster.paint_composite": {"paint composite"},
    "spa.authoring.raster.paint_native": {"paint line"},
}
# Plan Steps whose Kernel can return a Cel rejection: (operation, input, Cel code).
# The Plan translates it in its own code; standalone `paint apply` does too.
PLAN_ROWS = [
    ("cel add", {"target": ADDRESS}, "cel_already_exists"),
    ("cel set", {"target": ADDRESS, "opacity": 0}, "cel_not_found"),
    ("motion apply", MOTION, "cel_not_found"),
    ("paint apply", PAINT, "cel_not_found"),
]


def _refuse(
    operation: str, request: dict, payload: dict, *, direct: bool = False
) -> tuple[FailureEnvelope, list[str]]:
    """Dispatch operation with a Kernel that returns payload, and return the failure.

    `direct` sends payload from the direct Kernel invoker that a Plan uses.
    Return the failure envelope and the names of the invoked handlers.
    """
    descriptor = next(item for item in OPERATIONS if item.name == operation)
    calls = []

    def invoke(_observation, handler, request_payload, _timeout):
        calls.append(handler.name)
        if "staged_sprite_file" in request_payload:
            Path(request_payload["staged_sprite_file"]).write_bytes(b"unverified")
        return KernelInvocationResult(
            payload, "/response.json", Diagnostics(exit_status=0)
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
        invoke_kernel_direct=invoke if direct else None,
        decode_png_input=decode_png_input,
    )
    outcome = dispatch(descriptor, json.dumps(request), {}, services, FAILURE_CODES)
    assert isinstance(outcome, FailureEnvelope)
    return outcome, calls


def _files(source: Path, target_file: Path, /, **options: object) -> dict:
    """Return a mutation request from source to target_file with options."""
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target_file),
        "in_place": False,
        "overwrite": True,
        **options,
    }


def _expected_details(code: str, role: str, addressed: dict, to_frame: int) -> dict:
    """Return the details that `raise_cel_rejection` gives for a typed code."""
    if code == "layer_missing":
        return {
            "kind": "layer_target",
            "address_role": role,
            "address": addressed["layer"],
        }
    if code == "cel_frame_out_of_bounds":
        return {
            "kind": "cel_frame_range",
            "from_frame": addressed["frame_number"],
            "to_frame": to_frame,
        }
    return {"kind": "cel_target", "target": addressed}


def _check_consumer(
    tmp_path: Path, operation: str, options: dict, role: str, code: str
) -> None:
    """Refuse operation with code at the role address, and check the failure."""
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    inputs = {source, target}
    if operation == "image get":
        request = {"sprite_file": str(source), **options}
    else:
        request = _files(source, target, **options)
    if operation == "image import":
        raster = tmp_path / "raster.png"
        Image.new("RGBA", (1, 1), (30, 40, 50, 255)).save(raster)
        request["raster_file"] = str(raster)
        inputs.add(raster)
    addressed = DESTINATION if role == "destination" else ADDRESS
    rejection = {
        "code": code,
        "message": "native refusal",
        "role": role,
        "frame_number": addressed["frame_number"],
    }
    outcome, calls = _refuse(operation, request, {"rejection": rejection})
    assert len(calls) == 1
    if code == "unknown_rejection":
        assert outcome.code == "kernel_response_invalid"
        assert outcome.category == "kernel_protocol"
    else:
        assert outcome.code == code
        assert outcome.category == "input"
        assert outcome.message == "native refusal"
        to_frame = 3 if operation == "motion apply" else addressed["frame_number"]
        assert outcome.details.model_dump(exclude_none=True) == _expected_details(
            code, role, addressed, to_frame
        )
    assert source.read_bytes() == b"source"
    assert target.read_bytes() == b"target"
    assert set(tmp_path.iterdir()) == inputs


@pytest.mark.parametrize(("operation", "options", "role"), FEATURE_ROWS)
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
    _check_consumer(tmp_path, operation, options, role, code)


@pytest.mark.parametrize(
    ("operation", "options", "role", "cel_code"),
    [pytest.param(*row, id=f"{row[0]}-{row[2]}") for row in DOCUMENT_ROWS],
)
@pytest.mark.parametrize(
    "code",
    ["layer_missing", "cel_frame_out_of_bounds", "cel_target", "unknown_rejection"],
)
def test_cel_rejection_through_each_document_consumer(
    tmp_path: Path,
    operation: str,
    options: dict,
    role: str,
    cel_code: str,
    code: str,
) -> None:
    """`cel_target` is the Cel target code of the row."""
    _check_consumer(
        tmp_path, operation, options, role, cel_code if code == "cel_target" else code
    )


@pytest.mark.parametrize(
    ("operation", "step_input", "cel_code"),
    [pytest.param(*row, id=row[0]) for row in PLAN_ROWS],
)
@pytest.mark.parametrize(
    "code",
    ["layer_missing", "cel_frame_out_of_bounds", "cel_target", "unknown_rejection"],
)
def test_plan_step_translates_a_cel_rejection_as_its_standalone_operation(
    tmp_path: Path, operation: str, step_input: dict, cel_code: str, code: str
) -> None:
    """The Plan failure equals the standalone failure, plus `step_number`.

    `cel_target` is the Cel target code of the row.
    """
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    rejection = {
        "code": cel_code if code == "cel_target" else code,
        "message": "native refusal",
        "role": "target",
        "frame_number": 2,
    }
    standalone, calls = _refuse(
        operation, _files(source, target, **step_input), {"rejection": rejection}
    )
    assert len(calls) == 1
    plan = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "overwrite": True,
        "steps": [{"operation": operation, "input": step_input}],
    }
    failure, calls = _refuse(
        "plan run",
        {"plan": plan},
        {"cel_rejection": {**rejection, "step_number": 1}},
        direct=True,
    )
    assert calls == ["plan_run"]
    if operation == "paint apply":
        # Standalone Paint translates only `cel_not_found`, in its own code.
        typed = code == "cel_target"
        assert (standalone.code == cel_code) is typed
        if typed:
            details = standalone.details.model_dump(exclude_none=True)
            assert details == {"kind": "cel_target", "target": ADDRESS}
    assert failure.code == standalone.code
    assert failure.category == standalone.category
    if code == "unknown_rejection" or standalone.code == "kernel_response_invalid":
        assert failure.code == "kernel_response_invalid"
    else:
        assert failure.message == standalone.message == "native refusal"
        assert failure.details.model_dump(
            exclude_none=True
        ) == standalone.details.model_dump(exclude_none=True) | {"step_number": 1}
    assert source.read_bytes() == b"source"
    assert target.read_bytes() == b"target"
    assert set(tmp_path.iterdir()) == {source, target}


def test_rows_cover_each_module_that_calls_the_cel_rejection_translation() -> None:
    root = Path(spa.__file__).parent
    callers = set()
    for file in root.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.Call)
            and "raise_cel_rejection"
            in (getattr(node.func, "id", None), getattr(node.func, "attr", None))
            for node in ast.walk(tree)
        ):
            parts = file.relative_to(root.parent).with_suffix("").parts
            callers.add(".".join(parts))
    assert callers == set(CALLERS)
    rows = {row[0] for row in FEATURE_ROWS} | {row[0] for row in DOCUMENT_ROWS}
    assert rows == set().union(*CALLERS.values())
    descriptors = {descriptor.name: descriptor for descriptor in OPERATIONS}
    for module, operations in CALLERS.items():
        for operation in operations:
            assert descriptors[operation].execute.__module__ == module, operation
    # The Plan Steps that can refuse a Cel target, with their own translation.
    cel_targets = {"cel_not_found", "cel_already_exists"}
    steps = {
        name
        for name, descriptor in ELIGIBLE_OPERATIONS.items()
        if cel_targets & set(descriptor.failure_codes)
    }
    assert {row[0] for row in PLAN_ROWS} == steps
