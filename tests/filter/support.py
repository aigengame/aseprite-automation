"""Real Aseprite fixtures and public Filter command helpers."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from spa.adapters.aseprite.invocation import prepare_invocation
from tests.support import process_diagnostics, spa


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
