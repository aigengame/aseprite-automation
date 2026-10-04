"""Observe a real Plan execution and corrupt selected Tileset receipts."""

import json
import runpy
import sys
from pathlib import Path

from spa.adapters import files as file_adapter
from spa.adapters.aseprite import aseprite

case, observations_file, cli, *arguments = sys.argv[1:]
observations = {"native_invocations": 0, "commits": 0}
original_invoke = aseprite.invoke_direct


class ObservedTargetFiles(file_adapter.LocalTargetFiles):
    def commit(self, staged, target, *, overwrite):
        observations["commits"] += 1
        return super().commit(staged, target, overwrite=overwrite)


def observed_invoke(*args):
    observations["native_invocations"] += 1
    result = original_invoke(*args)
    assert Path(args[2]["staged_sprite_file"]).is_file()
    if case == "cel_grid":
        result.payload["steps"][0]["result"]["tilemap_creation"]["tileset"]["grid"][
            "tile_size"
        ]["width"] = 3
    elif case == "collection_order":
        # Keep the removal receipt internally consistent but change its retained
        # Tileset: it must still agree with the final native Sprite.
        removal = result.payload["steps"][-1]["result"]
        removal["before_tilesets"][1]["base_index"] = 82
        removal["tilesets"][0]["base_index"] = 82
    return result


def unexpected(*_args, **_kwargs):
    raise AssertionError("Plan must use one native invocation and its live handlers")


file_adapter.LocalTargetFiles = ObservedTargetFiles
aseprite.invoke_direct = observed_invoke
aseprite.probe = unexpected
aseprite.invoke = unexpected
sys.argv = [cli, *arguments]
try:
    runpy.run_path(cli, run_name="__main__")
finally:
    Path(observations_file).write_text(json.dumps(observations), encoding="utf-8")
