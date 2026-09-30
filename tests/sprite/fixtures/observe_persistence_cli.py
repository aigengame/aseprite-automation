"""Instrument native persistence and Target Commit without replacing either."""

import json
import runpy
import sys
from pathlib import Path

from spa import file_adapter
from spa.runtime import aseprite

case, observation_file, cli, *arguments = sys.argv[1:]
observations = {"handler_invocations": 0, "probe_invocations": 0, "commits": 0}
native_file = Path(observation_file).with_suffix(".native.json")
original_run = aseprite._run


class ObservedTargetFiles(file_adapter.LocalTargetFiles):
    def commit(self, staged, target, *, overwrite):
        observations["commits"] += 1
        return super().commit(staged, target, overwrite=overwrite)


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
aseprite._run = observed_run
sys.argv = [cli, *arguments]
try:
    runpy.run_path(cli, run_name="__main__")
finally:
    if native_file.exists():
        observations.update(json.loads(native_file.read_text()))
    Path(observation_file).write_text(json.dumps(observations), encoding="utf-8")
