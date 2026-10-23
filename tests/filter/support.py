"""Filter staging evidence and real Aseprite request and fixture helpers."""

import json
import sys
from copy import deepcopy
from dataclasses import replace
from importlib.resources import files
from pathlib import Path

from spa.adapters.files import LocalTargetFiles
from spa.application.surface import OPERATIONS
from spa.authoring.raster.color_curve import ColorCurveRequest, color_curve
from spa.authoring.raster.filter import BrightnessContrastRequest
from spa.authoring.raster.replace_color import ReplaceColorRequest, replace_color
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
# The Aseprite adapter resolves Kernel resources in the same package.
KERNEL = Path(str(files("spa.kernel")))


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


def operation_filter_names():
    """Return the `spa filter` operation names in OPERATIONS, in order."""
    return [
        descriptor.name.removeprefix("filter ")
        for descriptor in OPERATIONS
        if descriptor.name.startswith("filter ")
    ]


def assert_malformed(caught, cause):
    """Assert a `response_malformed` RuntimeIssue whose cause contains cause.

    caught is the `pytest.raises` result. cause is the text of the validator
    that refused the evidence.
    """
    assert caught.value.kind == "response_malformed"
    assert cause in str(caught.value.__cause__), caught.value.__cause__


def assert_unpublished(source, target, staged):
    assert source.read_bytes() == b"original source"
    assert target.read_bytes() == b"preexisting target"
    assert len(staged) == 1
    assert not staged[0].exists()


def brightness_contrast_evidence():
    """Return valid `spa filter brightness-contrast` evidence for one RGB Cel."""
    result = filter_evidence()
    result.update(
        brightness=10,
        contrast=0,
        requested_tileset_mode=None,
        observed_tileset_mode=None,
        changed_tiles=[],
    )
    for image in result["images"]:
        image["image_kind"] = "ordinary"
    return result


def hue_evidence():
    """Return valid `spa filter hue-saturation` evidence for one RGB Cel."""
    result = filter_cel_evidence()
    result["adjustment"] = {
        "mode": "hsl-multiply",
        "hue": 0,
        "saturation": 0,
        "lightness": 10,
    }
    result["alpha"] = None
    return result


def operation_case(name):
    """Return `(response, parameters, request_type, execute)` for a pixel Filter.

    name is `color-curve` or `replace-color`. The response is valid evidence
    for one RGB Cel and the parameters.
    """
    response = hue_evidence()
    for field in ("application", "palette_indexes", "adjustment", "alpha"):
        del response[field]
    if name == "color-curve":
        parameters = {"points": [{"input": 0, "output": 255}]}
        request_type, execute = ColorCurveRequest, color_curve
    else:
        parameters = {
            "from": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 255},
            "to": {"kind": "rgba", "red": 255, "green": 255, "blue": 255, "alpha": 255},
            "tolerance": 0,
        }
        response["changed_pixel_count"] = 1
        request_type, execute = ReplaceColorRequest, replace_color
    response.update(parameters)
    return response, parameters, request_type, execute


def despeckle_evidence():
    """Return valid `spa filter despeckle` evidence for a 3-by-1 window."""
    response = filter_cel_evidence()
    response.update(
        width=3, height=1, tiled_mode="none", anchor={"x": 1, "y": 0}, sample_count=3
    )
    return response


def setup_brightness_contrast(tmp_path, response=None, crash=False):
    """Return a Brightness/Contrast request and the staging of setup_filter_staging."""
    services, source, target, staged = setup_filter_staging(tmp_path, response, crash)
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
    return request, services, source, target, staged
