"""CLI request transport shared by the native Paint tests."""

import json
import os

from tests.support import spa


def call_spa(*command: str, **request: object) -> tuple[int, dict]:
    run = spa(
        *command,
        "--input-json",
        "-",
        stdin=json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"], **request}),
    )
    assert run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)
