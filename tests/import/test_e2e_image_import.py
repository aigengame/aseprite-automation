"""Compatible raster insertion through the installed CLI and real Aseprite."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image

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


def _create(runtime, source: Path, **params: str) -> None:
    with tempfile.TemporaryDirectory(prefix="spa-import-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        arguments = [str(prepared.executable), "--batch"]
        for key, value in {"out": str(source), **params}.items():
            arguments.extend(["--script-param", f"{key}={value}"])
        run = subprocess.run(
            [
                *arguments,
                "--script",
                str(Path(__file__).parent / "fixtures/import_target.lua"),
            ],
            env=prepared.environment,
            text=True,
            capture_output=True,
            check=False,
        )
    assert run.returncode == 0, process_diagnostics(run)


def _import(source: Path, raster: Path, target: Path, **extra):
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": source == target,
        "overwrite": True,
        "raster_file": str(raster),
        "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
        "position": {"x": -1, "y": 1},
        **extra,
    }
    run = spa("image", "import", "--input-json", json.dumps(request))
    assert run.stdout, process_diagnostics(run)
    return run.returncode, json.loads(run.stdout)


def test_import_rgba_preserves_complete_pixels_and_off_canvas_placement(
    tmp_path, runtime
):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    _create(runtime, source)
    pixels = bytes([10, 20, 30, 255, 60, 70, 80, 128, 90, 100, 110, 0, 0, 0, 0, 0])
    Image.frombytes("RGBA", (4, 1), pixels).save(raster)
    original, png = source.read_bytes(), raster.read_bytes()
    code, result = _import(source, raster, target)
    assert code == 0, json.dumps(result, indent=2)
    assert result["persisted_reopen_verified"] is True
    assert result["cel"]["frame_number"] == 2
    assert result["cel"]["layer_path"] == [1]
    assert result["cel"]["image_bounds"] == {"x": -1, "y": 1, "width": 4, "height": 1}
    assert result["cel"]["opacity"] == 255
    assert result["cel"]["z_index"] == 0
    assert result["cel"]["linked_cels"] == []
    assert result["raster_file"]["sha256"] == hashlib.sha256(png).hexdigest()
    assert result["image"]["stored_content_digest"] == {
        "algorithm": "fnv1a64",
        "value": "2d20e989cbe59ace",
    }
    assert (
        result["image"]["rgba_content_digest"]
        == result["image"]["stored_content_digest"]
    )
    assert source.read_bytes() == original
    assert raster.read_bytes() == png
    read = spa(
        "image",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(target),
                "source": {
                    "kind": "individual",
                    "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
                    "rectangle": {"x": 0, "y": 0, "width": 4, "height": 1},
                },
            }
        ),
    )
    assert read.returncode == 0, read.stdout
    colors = [run["color"] for run in json.loads(read.stdout)["snapshot"]["rows"][0]]
    assert [(c["red"], c["green"], c["blue"], c["alpha"]) for c in colors] == list(
        zip(*[iter(pixels)] * 4)
    )
