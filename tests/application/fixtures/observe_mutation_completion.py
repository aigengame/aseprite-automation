"""Observe the installed CLI's completion boundary and inject bounded failures."""

import json
import runpy
import sys
from pathlib import Path

from spa.adapters import files as file_adapter
from spa.adapters.aseprite import aseprite
from spa.contracts.ports import ProcessEvidence, RuntimeIssue, TargetCommitEvidence

case, observation_file, cli, *arguments = sys.argv[1:]
events = []
observations = {"events": events, "native_invocations": 0, "commits": 0}
original_probe = aseprite.probe
original_invoke = aseprite.invoke


def process_failure():
    raise RuntimeIssue(
        "process_failed",
        "Injected process failure",
        ProcessEvidence("test-aseprite", 13),
    )


class ObservedTargetFiles(file_adapter.LocalTargetFiles):
    def same_publication_entry(self, source, target):
        events.append("identity")
        if case == "identity" and events.count("identity") == 2:
            raise OSError("Injected identity observation failure")
        return super().same_publication_entry(source, target)

    def staged_path(self, target):
        events.append("stage")
        staged = super().staged_path(target)
        observations["staged"] = str(staged)
        return staged

    def commit(self, staged, target, *, overwrite):
        events.append("commit")
        if case == "commit":
            raise RuntimeIssue(
                "target_commit_failed",
                "Injected publication failure",
                TargetCommitEvidence(str(target), "replace_failed"),
            )
        result = super().commit(staged, target, overwrite=overwrite)
        observations["commits"] += 1
        return result

    def discard(self, staged):
        events.append("discard")
        super().discard(staged)
        observations["discarded"] = not staged.exists()


def observed_probe(*args, **kwargs):
    events.append("probe")
    if case == "probe":
        process_failure()
    return original_probe(*args, **kwargs)


def observed_invoke(observation, handler, payload, timeout):
    events.append("invoke")
    if case == "invocation":
        Path(payload["staged_sprite_file"]).write_bytes(b"partial native output")
        process_failure()
    observations["native_invocations"] += 1
    result = original_invoke(observation, handler, payload, timeout)
    assert Path(payload["staged_sprite_file"]).is_file()
    if case == "evidence":
        result.payload["persisted_reopen_verified"] = False
    elif case == "postcondition":
        if handler.name == "motion_apply":
            result.payload["cels"][0]["after"]["opacity"] = 1
        else:
            result.payload["cel"]["frame_number"] = 2
    return result


file_adapter.LocalTargetFiles = ObservedTargetFiles
aseprite.probe = observed_probe
aseprite.invoke = observed_invoke
sys.argv = [cli, *arguments]
try:
    runpy.run_path(cli, run_name="__main__")
finally:
    Path(observation_file).write_text(json.dumps(observations), encoding="utf-8")
