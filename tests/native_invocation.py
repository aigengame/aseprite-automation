"""Run the installed SPA command and Lua fixtures against a real Aseprite.

`run` and `expect_success` use one `aseprite` rule and validate each envelope
against the schema of its command, in process. `run_lua` runs one Lua fixture
with the GUI resource that runtime discovery found.
"""

import json
import os
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator, ValidationError

from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import OPERATIONS
from spa.contracts.operation import ACCESS_FAILURE_CODES
from spa.contracts.ports import RuntimeObservation
from spa.contracts.public import failure_schema
from tests.support import process_diagnostics, spa

_DESCRIPTORS = {descriptor.name: descriptor for descriptor in OPERATIONS}


@dataclass(frozen=True)
class Outcome:
    returncode: int
    envelope: dict[str, Any]
    process: subprocess.CompletedProcess[str]


@cache
def _validator(command: str, status: str) -> Draft202012Validator:
    if command == "spa":
        return Draft202012Validator(
            failure_schema(ACCESS_FAILURE_CODES, "spa", FAILURE_CODES)
        )
    schema = _DESCRIPTORS[command].schema(FAILURE_CODES)
    if status == "success":
        return Draft202012Validator(schema.result_schema)
    return Draft202012Validator(schema.failure_schema)


def validate_envelope(command: str, envelope: dict[str, Any]) -> None:
    """Validate an envelope against the schema of command.

    An access failure (operation `spa`) uses the access failure schema.
    """
    if envelope.get("operation") == "spa":
        _validator("spa", "failure").validate(envelope)
    else:
        _validator(command, str(envelope.get("status"))).validate(envelope)


def run(
    command: str,
    request: Mapping[str, Any],
    *,
    transport: Literal["argv", "stdin"] = "argv",
    aseprite: str | Path | None = None,
) -> Outcome:
    """Run `spa <command>` with request, and return its validated envelope.

    A runtime command gets `aseprite`, or the `SPA_TEST_ASEPRITE` value. The
    request itself stays unchanged.
    """
    assert "aseprite" not in request, "give the Aseprite path as aseprite="
    payload = dict(request)
    descriptor = _DESCRIPTORS.get(command)
    if descriptor is not None and descriptor.requires_runtime:
        selected = os.environ["SPA_TEST_ASEPRITE"] if aseprite is None else aseprite
        payload["aseprite"] = str(selected)
    text = json.dumps(payload)
    if transport == "argv":
        process = spa(*command.split(), "--input-json", text)
    else:
        process = spa(*command.split(), "--input-json", "-", stdin=text)
    try:
        envelope = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(process_diagnostics(process)) from error
    try:
        validate_envelope(command, envelope)
    except ValidationError as error:
        error.add_note(process_diagnostics(process))
        raise
    return Outcome(process.returncode, envelope, process)


def expect_success(
    command: str,
    request: Mapping[str, Any],
    *,
    transport: Literal["argv", "stdin"] = "argv",
    aseprite: str | Path | None = None,
) -> dict[str, Any]:
    """Return the success envelope of `spa <command>`, or fail with diagnostics."""
    outcome = run(command, request, transport=transport, aseprite=aseprite)
    assert outcome.returncode == 0 and outcome.envelope["status"] == "success", (
        process_diagnostics(outcome.process)
    )
    return outcome.envelope


def _script_parameter(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def run_lua(
    script: Path, runtime: RuntimeObservation, **params: object
) -> subprocess.CompletedProcess[str]:
    """Run one Lua fixture in batch mode, and return the completed process.

    Each keyword becomes one `--script-param`. The caller asserts the exit status;
    `process_diagnostics` describes the process when the assertion fails.
    """
    arguments = [
        item
        for key, value in params.items()
        for item in ("--script-param", f"{key}={_script_parameter(value)}")
    ]
    with tempfile.TemporaryDirectory(prefix="spa-lua-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        return subprocess.run(
            [str(prepared.executable), "--batch", *arguments, "--script", str(script)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
