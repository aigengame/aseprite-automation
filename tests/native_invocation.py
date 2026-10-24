"""Run the installed SPA command and Lua fixtures against a real Aseprite.

`run` and `expect_success` use one `aseprite` rule and validate each envelope
against the schema of its command, in process. `run_lua` runs one Lua fixture
with the GUI resource that runtime discovery found. `render_frame` is the render
oracle: it exports one Frame through `spa export image`.

Only `run_lua` adds a deadline. `run` and `expect_success` add none: the product
deadline (`timeout_seconds`) already bounds each Aseprite process that SPA starts.
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
from PIL import Image

from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import OPERATIONS
from spa.contracts.operation import ACCESS_FAILURE_CODES
from spa.contracts.ports import RuntimeObservation
from spa.contracts.public import failure_schema
from tests.support import process_diagnostics, spa

_DESCRIPTORS = {descriptor.name: descriptor for descriptor in OPERATIONS}

LUA_FIXTURE_DEADLINE_SECONDS = 120
"""The deadline of each `run_lua` Aseprite launch, for every caller."""


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


def validate_envelope(command: str, envelope: object) -> None:
    """Validate an envelope against the schema of command.

    An access failure (operation `spa`) and each envelope of a command that is
    not registered use the access failure schema. A value that is not an object
    fails the failure schema of command.
    """
    fields: dict[str, Any] = envelope if isinstance(envelope, dict) else {}
    if fields.get("operation") == "spa" or command not in _DESCRIPTORS:
        _validator("spa", "failure").validate(envelope)
    else:
        _validator(command, str(fields.get("status"))).validate(envelope)


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


def render_frame(source: Path, frame: int) -> Image.Image:
    """Export one Frame of source as a visible-canvas PNG, and return it as RGBA.

    The PNG goes to a temporary directory, so the caller's directory does not
    change.
    """
    with tempfile.TemporaryDirectory(prefix="spa-render-frame-") as work:
        output = Path(work) / "frame.png"
        expect_success(
            "export image",
            {
                "source_sprite_file": str(source),
                "destination": {"path": str(output), "if_exists": "fail"},
                "frame_number": frame,
                "export_image_area": {"kind": "canvas"},
                "layer_composition": {"mode": "visible"},
                "composition_color_mode": "preserve",
                "color_mode": "preserve",
                "color_profile": "preserve",
                "transparency": "preserve",
            },
        )
        with Image.open(output) as image:
            return image.convert("RGBA")


def _script_parameter(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _captured(output: bytes | str | None) -> str:
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output or ""


def run_lua(
    script: Path, runtime: RuntimeObservation, **params: object
) -> subprocess.CompletedProcess[str]:
    """Run one Lua fixture in batch mode, and return the completed process.

    Each keyword becomes one `--script-param`. The caller asserts the exit status;
    `process_diagnostics` describes the process when the assertion fails. When
    the launch does not exit before `LUA_FIXTURE_DEADLINE_SECONDS`, the Aseprite
    process is stopped, and the test fails with the script, its parameters and the
    output captured until then.
    """
    values = [f"{key}={_script_parameter(value)}" for key, value in params.items()]
    arguments = [item for value in values for item in ("--script-param", value)]
    with tempfile.TemporaryDirectory(prefix="spa-lua-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        try:
            return subprocess.run(
                [
                    str(prepared.executable),
                    "--batch",
                    *arguments,
                    "--script",
                    str(script),
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                env=prepared.environment,
                timeout=LUA_FIXTURE_DEADLINE_SECONDS,
            )
        except subprocess.TimeoutExpired as expired:
            # subprocess.run stopped and reaped the process before it raised.
            raise AssertionError(
                f"Lua fixture did not exit in {expired.timeout:g} s: {script}\n"
                f"parameters: {' '.join(values)}\n"
                f"stdout:\n{_captured(expired.stdout)}\n"
                f"stderr:\n{_captured(expired.stderr)}"
            ) from None
