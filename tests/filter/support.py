"""Filter staging evidence and real Aseprite command helpers."""

import json
import os
import subprocess
import tempfile
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from spa.adapters.aseprite.invocation import prepare_invocation
from spa.adapters.files import LocalTargetFiles
from spa.contracts.ports import KernelInvocationResult
from spa.contracts.public import Diagnostics
from tests.support import (
    operation_services,
    process_diagnostics,
    runtime_observation,
    spa,
)


def native_script(runtime, script, **params):
    with tempfile.TemporaryDirectory(prefix="spa-filter-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        args = [str(prepared.executable), "--batch"]
        for name, value in params.items():
            args.extend(["--script-param", f"{name}={value}"])
        result = subprocess.run(
            [*args, "--script", str(Path(__file__).parent / "fixtures" / script)],
            env=prepared.environment,
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 0, process_diagnostics(result)


def run(*command, **request):
    result = spa(
        *command,
        "--input-json",
        json.dumps(
            {
                **request,
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


def apply(source, target, application, brightness=50, contrast=0, **intent):
    return run(
        "filter",
        "brightness-contrast",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=intent.pop("in_place", False),
        overwrite=intent.pop("overwrite", False),
        application=application,
        brightness=brightness,
        contrast=contrast,
        **intent,
    )


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
    response = source.with_suffix(".observed.json")
    native_script(runtime, "observe.lua", source=source, response=response)
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
