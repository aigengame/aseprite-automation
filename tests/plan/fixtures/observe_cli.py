"""Observe real CLI boundary calls and inject invalid native responses for E2E tests."""

import json
import runpy
import sys
from pathlib import Path

from spa import file_adapter
from spa.runtime import aseprite

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
    if case == "malformed_step":
        result.payload["steps"][1]["result"]["cel"]["frame_number"] = 4
    elif case == "contradictory_count":
        assert Path(args[2]["staged_sprite_file"]).is_file()
        result.payload["steps"][0]["result"]["before_cel_count"] = 0
    elif case == "unverified_save":
        result.payload["persisted_reopen_verified"] = False
    return result


def unexpected(*_args, **_kwargs):
    raise AssertionError("Plan must not launch a separate probe or standalone handler")


# Install observers before the installed entry point constructs its real adapters.
file_adapter.LocalTargetFiles = ObservedTargetFiles
aseprite.invoke_direct = observed_invoke
aseprite.probe = unexpected
aseprite.invoke = unexpected
sys.argv = [cli, *arguments]
try:
    runpy.run_path(cli, run_name="__main__")
finally:
    Path(observations_file).write_text(json.dumps(observations), encoding="utf-8")
