"""Run the installed CLI with observers on one adapter seam, for e2e tests.

Usage: observe_cli.py <seam> <case> <observations> <cli> <argument>...

The observers replace SPA adapters before the entry point constructs them. Each
seam counts Target Commits and writes its observations as JSON when the CLI
stops. The seam selects what else the observers do:

- `invoke_direct`: count the native invocations of a Plan, change the native
  response as case requires, and refuse a separate probe or standalone handler.
- `run`: count the probe and handler processes, and run each handler inside
  `observe_cli.lua`. That wrapper injects the native I/O fault of case and
  records what the handler did.
"""

import json
import runpy
import sys
from pathlib import Path

from spa.adapters import files as file_adapter
from spa.adapters.aseprite import aseprite

SEAMS = ("invoke_direct", "run")
# Cases whose native Plan response must come with a staged Sprite file.
STAGED_CASES = {
    "contradictory_count",
    "contradictory_high_count",
    "none",
    "cel_grid",
    "collection_order",
}

seam, case, observations_file, cli, *arguments = sys.argv[1:]
assert seam in SEAMS, f"unknown seam {seam!r}; use one of {SEAMS}"
observations = {"commits": 0}
native_file = Path(observations_file).with_suffix(".native.json")
original_invoke = aseprite.invoke_direct
original_run = aseprite._run


class ObservedTargetFiles(file_adapter.LocalTargetFiles):
    def commit(self, staged, target, *, overwrite):
        observations["commits"] += 1
        return super().commit(staged, target, overwrite=overwrite)


def corrupt(payload):
    """Change the native Plan response as case requires."""
    if case == "malformed_step":
        payload["steps"][1]["result"]["cel"]["frame_number"] = 4
    elif case in ("contradictory_count", "contradictory_high_count"):
        facts = payload["steps"][0]["result"]
        count = 0 if case == "contradictory_count" else 2
        if "before_cel_count" in facts:
            assert facts["before_cel_count"] == 1
            facts["before_cel_count"] = count
        else:
            assert facts["sprite"]["metadata"]["cel_count"] == 1
            facts["sprite"]["metadata"]["cel_count"] = count
    elif case == "unverified_save":
        payload["persisted_reopen_verified"] = False
    elif case == "motion_coverage":
        payload["steps"][0]["result"]["cels"].pop()
    elif case == "motion_count":
        payload["steps"][0]["result"]["before_cel_count"] += 1
    elif case == "cel_grid":
        payload["steps"][0]["result"]["tilemap_creation"]["tileset"]["grid"][
            "tile_size"
        ]["width"] = 3
    elif case == "collection_order":
        # Keep the removal receipt internally consistent but change its retained
        # Tileset: it must still agree with the final native Sprite.
        removal = payload["steps"][-1]["result"]
        removal["before_tilesets"][1]["base_index"] = 82
        removal["tilesets"][0]["base_index"] = 82


def observed_invoke(*args):
    observations["native_invocations"] += 1
    result = original_invoke(*args)
    if case in STAGED_CASES:
        assert Path(args[2]["staged_sprite_file"]).is_file()
    corrupt(result.payload)
    return result


def unexpected(*_args, **_kwargs):
    raise AssertionError(
        "Plan must use one native invocation and its live handlers; it must not "
        "launch a separate probe or standalone handler"
    )


def observed_run(command, *args, **kwargs):
    script_index = command.index("--script") + 1
    script = Path(command[script_index])
    if script.stem == "probe":
        observations["probe_invocations"] += 1
    if script.stem in {"cel_relationship", "motion_apply", "plan_run"}:
        observations["handler_invocations"] += 1
        command = list(command)
        command[script_index] = str(Path(__file__).with_suffix(".lua"))
        command[script_index - 1 : script_index - 1] = [
            "--script-param",
            f"test_handler={script}",
            "--script-param",
            f"test_case={case}",
            "--script-param",
            f"test_observations={native_file}",
        ]
    return original_run(command, *args, **kwargs)


file_adapter.LocalTargetFiles = ObservedTargetFiles
if seam == "invoke_direct":
    observations["native_invocations"] = 0
    aseprite.invoke_direct = observed_invoke
    aseprite.probe = unexpected
    aseprite.invoke = unexpected
else:
    observations.update(handler_invocations=0, probe_invocations=0)
    aseprite._run = observed_run
sys.argv = [cli, *arguments]
try:
    runpy.run_path(cli, run_name="__main__")
finally:
    if native_file.exists():
        observations.update(json.loads(native_file.read_text()))
    Path(observations_file).write_text(json.dumps(observations), encoding="utf-8")
