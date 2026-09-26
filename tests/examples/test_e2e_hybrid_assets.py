"""Frozen raster handoff and complete hybrid delivery through installed SPA."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from examples.wizard_cast_v2.build import build
from examples.wizard_cast_v2.verify import compare_delivery, inspect_build
from examples.wizard_cast_v2.workflow import Spa
from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from tests.examples.test_e2e_wizard_assets import inspect_stored_pixels

pytestmark = [pytest.mark.e2e, pytest.mark.slow]
EXAMPLE = Path(__file__).resolve().parents[2] / "examples/wizard_cast_v2"

# Test-only read access supplements public structural inspection. Raw RGBA bytes
# are temporary; only SHA-256 digests survive in the comparison result. The stream
# includes transparent and hidden pixels, which scene PNGs cannot establish.
_NATIVE_PIXELS = """
local sprite = assert(app.open(app.params.source))
local pixels = assert(io.open(app.params.pixels, "wb"))
local cels = {}
local offset = 0
for _, cel in ipairs(sprite.cels) do
  local image = cel.image
  local length = image.width * image.height * 4
  cels[#cels + 1] = {
    frame = cel.frameNumber, layer = cel.layer.name,
    x = cel.position.x, y = cel.position.y, opacity = cel.opacity,
    width = image.width, height = image.height,
    offset = offset, length = length,
  }
  for y = 0, image.height - 1 do
    local row = {}
    for x = 0, image.width - 1 do
      local pixel = image:getPixel(x, y)
      row[#row + 1] = string.char(
        app.pixelColor.rgbaR(pixel), app.pixelColor.rgbaG(pixel),
        app.pixelColor.rgbaB(pixel), app.pixelColor.rgbaA(pixel))
    end
    pixels:write(table.concat(row))
  end
  offset = offset + length
end
pixels:close()
sprite:close()
local output = assert(io.open(app.params.out, "wb"))
output:write(json.encode(cels))
output:close()
"""


def _stored_pixel_digests(source: Path, aseprite: str, workspace: Path) -> list[dict]:
    observation = probe(RuntimeRequest(aseprite=aseprite), PROBE_RESOURCES)
    with tempfile.TemporaryDirectory(dir=workspace) as temporary:
        work = Path(temporary)
        script = work / "inspect.lua"
        script.write_text(_NATIVE_PIXELS)
        prepared = prepare_invocation(
            Path(observation.canonical_path), Path(observation.resource_path), work
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"source={source}",
                "--script-param",
                f"pixels={work / 'pixels.bin'}",
                "--script-param",
                f"out={work / 'cels.json'}",
                "--script",
                str(script),
            ],
            env=prepared.environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == 0, run.stdout + run.stderr
        cels = json.loads((work / "cels.json").read_text())
        data = (work / "pixels.bin").read_bytes()
        for cel in cels:
            offset, length = cel.pop("offset"), cel.pop("length")
            cel["rgba_sha256"] = hashlib.sha256(
                data[offset : offset + length]
            ).hexdigest()
        return cels


def _runtime() -> tuple[str, str]:
    return (
        os.environ.get("SPA_TEST_INSTALLED_CLI", str(Path(".venv/bin/spa").resolve())),
        os.environ["SPA_TEST_ASEPRITE"],
    )


def test_complete_hybrid_recipe_reproduces_delivery(tmp_path: Path) -> None:
    cli, aseprite = _runtime()
    fresh = tmp_path / "fresh"
    build(cli, aseprite, fresh)
    compare_delivery(fresh, EXAMPLE / "godot/content/wizard_assets")
    generated = inspect_build(fresh)["sprite"]
    spa = Spa(cli, aseprite, fresh / "evidence/delivery-inspection.jsonl")
    palette = json.loads((fresh / "recipe.json").read_text())["palette"]
    generated_sources = sorted((fresh / "source").glob("*.aseprite"))
    assert {path.name for path in generated_sources} == {
        path.name for path in (EXAMPLE / "source").glob("*.aseprite")
    }
    for source in generated_sources:
        retained = EXAMPLE / "source" / source.name
        structures = [
            spa.call(
                "sprite get",
                sprite_file=str(path),
                inspection_scope=["frames", "layers", "cels", "tags"],
            )
            for path in (source, retained)
        ]
        assert {key: structures[0][key] for key in generated} == {
            key: structures[1][key] for key in generated
        }, source.name
        native = inspect_stored_pixels(
            source, aseprite, fresh / "evidence" / f"{source.stem}-stored.json"
        )
        assert set(native["stored_colors"]) <= {
            color.lower() for color in palette.values()
        }, source.name
        assert _stored_pixel_digests(
            source, aseprite, tmp_path
        ) == _stored_pixel_digests(retained, aseprite, tmp_path), source.name
