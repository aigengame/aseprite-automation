"""Force a native save failure after Paint, through the real installed CLI."""

import json
import runpy
import sys
from pathlib import Path

from spa import file_adapter

observations_file, cli, *arguments = sys.argv[1:]
observations = {"commits": 0, "discarded": False}


class FailedSaveTargetFiles(file_adapter.LocalTargetFiles):
    def staged_path(self, target):
        staged = super().staged_path(target)
        blocked_parent = staged.parent / "blocked-stage-parent"
        blocked_parent.write_bytes(b"not a directory")
        return blocked_parent / staged.name

    def commit(self, staged, target, *, overwrite):
        observations["commits"] += 1
        return super().commit(staged, target, overwrite=overwrite)

    def discard(self, staged):
        super().discard(staged)
        observations["discarded"] = True


# Fail the outbound staging boundary; native drawing and save remain real.
file_adapter.LocalTargetFiles = FailedSaveTargetFiles
sys.argv = [cli, *arguments]
try:
    runpy.run_path(cli, run_name="__main__")
finally:
    Path(observations_file).write_text(json.dumps(observations), encoding="utf-8")
