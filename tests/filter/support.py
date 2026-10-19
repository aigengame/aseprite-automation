"""Filter staging evidence and real Aseprite request and fixture helpers."""

import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from spa.adapters.files import LocalTargetFiles
from spa.application.surface import OPERATIONS
from spa.contracts.ports import KernelInvocationResult, PackagedHandler
from spa.contracts.public import Diagnostics
from tests.native_invocation import run, run_lua
from tests.support import (
    inject_palette_change,
    operation_services,
    process_diagnostics,
    runtime_observation,
)

FIXTURES = Path(__file__).parent / "fixtures"
KERNEL = Path(__file__).resolve().parents[2] / "src" / "spa" / "kernel"


def filter_handler(operation: str) -> PackagedHandler:
    """Return the Kernel handler of `spa filter <operation>`.

    The handler is the `<operation>_run` PackagedHandler in the module that
    defines the execute function of the descriptor. A new Filter that follows
    this name rule needs no edit in the tests that use this function.
    """
    (descriptor,) = (item for item in OPERATIONS if item.name == f"filter {operation}")
    module = sys.modules[descriptor.execute.__module__]
    name = f"{operation.replace('-', '_')}_run"
    handlers = {
        id(value): value
        for value in vars(module).values()
        if isinstance(value, PackagedHandler) and value.name == name
    }
    assert len(handlers) == 1, (operation, module.__name__, list(handlers.values()))
    return next(iter(handlers.values()))


def kernel_resources(handler: PackagedHandler) -> dict[str, Path]:
    """Map each support resource parameter of handler to its Kernel source file."""
    return {
        resource.parameter_name: KERNEL / resource.package_path
        for resource in handler.support_resources
    }


def apply(source, target, application, brightness=50, contrast=0, **intent):
    """Run `spa filter brightness-contrast` and return `(returncode, envelope)`.

    This adds the Source and Target fields, `in_place` and `overwrite` from
    intent (default False), and the brightness and contrast defaults.
    """
    outcome = run(
        "filter brightness-contrast",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": intent.pop("in_place", False),
            "overwrite": intent.pop("overwrite", False),
            "application": application,
            "brightness": brightness,
            "contrast": contrast,
            **intent,
        },
    )
    return outcome.returncode, outcome.envelope


def pixels(mode="rgb", **options):
    return {
        "kind": "pixels",
        "color_mode": mode,
        "cels_target": {
            "kind": "selected",
            "layers": [{"layer_path": [1]}],
            "frame_numbers": [1],
        },
        "channels": {
            "kind": "components",
            "names": ["gray"] if mode == "grayscale" else ["red", "green", "blue"],
        },
        **options,
    }


def observe_images(runtime, source):
    """Run `observe.lua` on source and return the Image observation it writes."""
    response = source.with_suffix(".observed.json")
    lua = run_lua(FIXTURES / "observe.lua", runtime, source=source, response=response)
    assert lua.returncode == 0, process_diagnostics(lua)
    return json.loads(response.read_text())


def palette_source(runtime, source, mode):
    """Create the Palette basis scene, then add a Palette change at Frame 2."""
    lua = run_lua(
        FIXTURES / "target_palette_basis.lua", runtime, source=source, mode=mode
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    colors = [(0, 0, 0, 0), (20, 0, 0, 255)]
    if mode == "indexed":
        colors.append((120, 0, 0, 255))
    inject_palette_change(source, colors, frame_number=2)


def palette_observation(runtime, source):
    """Run `target_palette_observe.lua` on source and return its observation."""
    response = source.with_suffix(".basis.json")
    lua = run_lua(
        FIXTURES / "target_palette_observe.lua",
        runtime,
        source=source,
        response=response,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    return json.loads(response.read_text())


def rgb_palette_colors(**options):
    return {
        "kind": "rgb-palette-colors",
        "palette_frame_number": 1,
        "indexes": [1],
        "cels_target": pixels()["cels_target"],
        "channels": {"kind": "components", "names": ["red"]},
        **options,
    }


def filter_evidence():
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


def filter_cel_evidence():
    result = filter_evidence()
    bounds = {"x": 0, "y": 0, "width": 1, "height": 1}
    result["cel_effects"] = [
        {**result["affected_cels"][0], "before": bounds, "after": deepcopy(bounds)}
    ]
    return result


def setup_filter_staging(tmp_path, response=None, crash=False):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"original source")
    target.write_bytes(b"preexisting target")
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
    return services, source, target, staged


def assert_unpublished(source, target, staged):
    assert source.read_bytes() == b"original source"
    assert target.read_bytes() == b"preexisting target"
    assert len(staged) == 1
    assert not staged[0].exists()
