"""Read native structure and every stored RGBA pixel without authoring via Lua."""

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from examples.wizard_cast_v2.workflow import Spa
from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest

# Inspection only: raw bytes live in a temporary directory. The Lua script never
# changes or saves the source. All production writes remain public SPA Operations.
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
local profile_ok = sprite.colorSpace == ColorSpace { sRGB = true }
  or sprite.colorSpace == ColorSpace()
sprite:close()
local output = assert(io.open(app.params.out, "wb"))
output:write(json.encode({ cels = cels, profile_ok = profile_ok }))
output:close()
"""


def inspect_native(source: Path, spa: Spa, workspace: Path) -> dict:
    reopened = spa.call(
        "sprite get",
        sprite_file=str(source),
        inspection_scope=["frames", "layers", "cels", "tags"],
    )
    observation = probe(RuntimeRequest(aseprite=spa.aseprite), PROBE_RESOURCES)
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
        native = json.loads((work / "cels.json").read_text())
        assert native["profile_ok"], f"Unexpected native color profile: {source}"
        cels = native["cels"]
        data = (work / "pixels.bin").read_bytes()
        colors = set()
        for cel in cels:
            offset, length = cel.pop("offset"), cel.pop("length")
            rgba = data[offset : offset + length]
            assert len(rgba) == length == cel["width"] * cel["height"] * 4
            assert all(alpha in (0, 255) for alpha in rgba[3::4]), source
            assert int(cel["x"]) == cel["x"] and int(cel["y"]) == cel["y"], source
            colors.update(
                "#" + rgba[index : index + 3].hex()
                for index in range(0, length, 4)
                if rgba[index + 3]
            )
            cel["rgba_sha256"] = hashlib.sha256(rgba).hexdigest()
        return {
            "structure": {
                key: reopened[key]
                for key in ("metadata", "frames", "layers", "cels", "tags")
            },
            "cels": cels,
            "stored_colors": sorted(colors),
        }


def compare_native(
    first: Path, second: Path, spa: Spa, workspace: Path, palette: set[str]
) -> None:
    """Fail on corrupt files, structural differences, or hidden RGBA differences."""
    left = inspect_native(first, spa, workspace)
    right = inspect_native(second, spa, workspace)
    for native in (left, right):
        assert set(native["stored_colors"]) <= palette, first.name
    assert left == right, f"Native structure or stored RGBA pixels differ: {first.name}"
