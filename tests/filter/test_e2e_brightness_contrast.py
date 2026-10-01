"""Brightness/Contrast uses Aseprite's native Filter, then verifies persistence."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
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
        in_place=False,
        overwrite=False,
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


def test_rgb_pixels_are_native_and_source_is_unchanged(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="rgb")
    before = source.read_bytes()
    code, result = apply(source, target, pixels())
    assert code == 0, result
    assert result["changed"] is True
    assert result["persisted_reopen_verified"] is True
    assert result["channels"] == {
        "kind": "components",
        "names": ["red", "green", "blue"],
    }
    assert len(result["images"]) == 1
    assert len(result["affected_cels"]) == 1
    assert source.read_bytes() == before
    native_script(runtime, "check_rgb.lua", source=target)


def test_grayscale_only_changes_gray_and_retains_alpha(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "source.lua", source=source, mode="grayscale")
    code, result = apply(source, target, pixels("grayscale"))
    assert code == 0, result
    native_script(runtime, "check_gray.lua", source=target)
