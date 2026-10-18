"""Rule tables over the public command tree.

A rule table states one rule that every command in a set obeys. Each row runs one
command through the CLI projection in process, with `run_cli` and the real file
adapters. Each Kernel port raises `PortReached`, so no Aseprite process starts and a
row that reaches the Kernel fails. The one exception is the `discovering` probe: it
uses the installed `invoke_kernel_direct`, because `plan run` discovers the runtime
in it. Its rows give an Aseprite path that discovery refuses before a process
starts. The expected exit status, category and code of a rule are literal values.
They do not come from the Operation Descriptor.

The rows of a table come from a predicate over `OPERATIONS`, so a new command gets a
row in each table that applies to it. A command that does not obey the rule needs an
exemption with a reason, and the guard of the table checks that the reason is still
true.
"""

import contextlib
import io
import json
import struct
import sys
import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache, partial
from pathlib import Path
from typing import Any, get_args

import click
import pytest
import typer.main
from jsonschema import Draft202012Validator

from spa.access.cli import build_app, run_cli
from spa.adapters.artifact_set import LocalArtifactSets
from spa.adapters.aseprite.aseprite import invoke_direct
from spa.adapters.aseprite.aseprite import probe as discover_and_probe
from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles, observe_script_file
from spa.adapters.gif import decode_gif
from spa.adapters.icc import verify_icc
from spa.adapters.palette_file import decode_palette_file
from spa.adapters.png import verify_png
from spa.adapters.png_input import decode_png_artifact, decode_png_input
from spa.adapters.sequence_png import decode_sequence_png
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import OPERATIONS, PROBE_RESOURCES
from spa.contracts.operation import OperationDescriptor
from spa.contracts.ports import OperationServices, RuntimeProbe
from spa.contracts.public import OperationSchema, RuntimeCapability, RuntimeRequest
from tests.support import runtime_observation

DESCRIPTORS: Mapping[str, OperationDescriptor[Any, Any]] = {
    descriptor.name: descriptor for descriptor in OPERATIONS
}

INPUT_REFUSAL = (2, "input", "invalid_request")


class PortReached(Exception):
    """A row reached a port that its rule must not reach."""


def _port(name: str) -> Callable[..., Any]:
    def reached(*_args: object, **_kwargs: object) -> Any:
        raise PortReached(name)

    return reached


def _capable_probe(_request: RuntimeRequest):
    return runtime_observation(*get_args(RuntimeCapability))


def _incapable_probe(_request: RuntimeRequest):
    return runtime_observation()


PROBES: Mapping[str, RuntimeProbe] = {
    "unreached": _port("probe_runtime"),
    "capable": _capable_probe,
    "incapable": _incapable_probe,
    # The installed probe. A row gives it an Aseprite path that discovery refuses
    # before a process starts.
    "discovering": partial(discover_and_probe, resources=PROBE_RESOURCES),
}


def _services(probe: str) -> OperationServices:
    direct = _port("invoke_kernel_direct")
    if probe == "discovering":
        # `plan run` discovers the runtime inside its direct Kernel invocation.
        direct = invoke_direct
    return OperationServices(
        probe_runtime=PROBES[probe],
        invoke_kernel=_port("invoke_kernel"),
        invoke_script=_port("invoke_script"),
        observe_script_file=observe_script_file,
        invoke_kernel_direct=direct,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
        artifact_sets=LocalArtifactSets(),
        decode_sequence_png=decode_sequence_png,
        decode_gif=decode_gif,
        verify_png=verify_png,
        verify_icc=verify_icc,
        decode_palette_file=decode_palette_file,
        decode_png_input=decode_png_input,
        decode_png_artifact=decode_png_artifact,
    )


@cache
def _app(probe: str) -> typer.Typer:
    return build_app(_services(probe), FAILURE_CODES)


_CLICK_COMMANDS: dict[typer.Typer, click.Command] = {}
_get_command = typer.main.get_command


def _cached_command(app: typer.Typer) -> click.Command:
    # `run_cli` converts the Typer app to a Click group on each call. The installed
    # CLI makes one call for each process; the rows make more than a thousand.
    if app not in _CLICK_COMMANDS:
        _CLICK_COMMANDS[app] = _get_command(app)
    return _CLICK_COMMANDS[app]


@dataclass(frozen=True)
class Outcome:
    exit_status: int
    envelope: dict[str, Any]

    @property
    def result(self) -> tuple[int, str | None, str | None]:
        return (
            self.exit_status,
            self.envelope.get("category"),
            self.envelope.get("code"),
        )

    @property
    def errors(self) -> list[tuple[list[Any], str]]:
        errors = self.envelope["details"]["errors"]
        return [(error["location"], error["code"]) for error in errors]


def every_command(_descriptor: OperationDescriptor[Any, Any]) -> bool:
    return True


def runtime_command(descriptor: OperationDescriptor[Any, Any]) -> bool:
    return descriptor.requires_runtime


def run_spa(argv: Sequence[str], probe: str = "unreached") -> Outcome:
    """Run `spa <argv>` in process and return its exit status and JSON output."""
    output = io.StringIO()
    saved = sys.argv, typer.main.get_command
    sys.argv = ["spa", *argv]
    typer.main.get_command = _cached_command
    exit_status = 0
    try:
        with contextlib.redirect_stdout(output):
            run_cli(_app(probe), FAILURE_CODES)
    except SystemExit as exit_:
        assert isinstance(exit_.code, int), exit_.code
        exit_status = exit_.code
    finally:
        sys.argv, typer.main.get_command = saved
    return Outcome(exit_status, json.loads(output.getvalue()))


def run_request(
    command: str, request: dict[str, Any], *argv: str, probe: str = "unreached"
) -> Outcome:
    """Run `spa <command>` with `request` as `--input-json` and more `argv`."""
    return run_spa(
        [*command.split(), "--input-json", json.dumps(request), *argv], probe
    )


@cache
def _schema(command: str) -> OperationSchema:
    return DESCRIPTORS[command].schema(FAILURE_CODES)


@cache
def _failure_validator(command: str) -> Draft202012Validator:
    return Draft202012Validator(_schema(command).failure_schema)


def validate_failure(command: str, envelope: dict[str, Any]) -> None:
    _failure_validator(command).validate(envelope)


# Minimal valid requests ----------------------------------------------------------


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data)
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


# One transparent RGBA pixel.
_INPUT_PNG = (
    b"\x89PNG\r\n\x1a\n"
    + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    + _png_chunk(b"IDAT", zlib.compress(b"\x00" * 5))
    + _png_chunk(b"IEND", b"")
)


@dataclass(frozen=True)
class _Files:
    directory: Path

    @property
    def source(self) -> Path:
        return self.directory / "source.aseprite"

    @property
    def target(self) -> Path:
        return self.directory / "target.aseprite"

    def input_png(self, name: str) -> Path:
        path = self.directory / f"in-{name}.png"
        path.write_bytes(_INPUT_PNG)
        return path


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        schema = root["$defs"][schema["$ref"].rsplit("/", 1)[-1]]
    return schema


def _string(name: str, schema: dict[str, Any], files: _Files) -> str:
    if "sprite_file" in name:
        return str(files.target if name.startswith("target") else files.source)
    pattern = schema.get("pattern", "")
    for extension in ("png", "json", "gif", "gpl", "aseprite", "lua"):
        if f"\\.{extension}" in pattern:
            return str(files.directory / f"out-{name}.{extension}")
    if name in ("path", "raster_file", "palette_file", "script"):
        return str(files.input_png(name))
    return "a" * max(1, schema.get("minLength", 1))


def _value(
    schema: dict[str, Any], root: dict[str, Any], files: _Files, name: str = ""
) -> Any:
    """Choose the first choice of each union and the lowest bound of each number."""
    schema = _resolve(schema, root)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    for key in ("oneOf", "anyOf"):
        if key in schema:
            choices = [
                choice
                for choice in schema[key]
                if _resolve(choice, root).get("type") != "null"
            ]
            return _value(choices[0], root, files, name)
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        chosen = list(schema.get("required", [])) + [
            key
            for key, value in properties.items()
            if key not in schema.get("required", [])
            and "const" in _resolve(value, root)
        ]
        if not chosen and properties:
            chosen = [next(iter(properties))]  # One of several exclusive addresses.
        return {
            key: _value(properties[key], root, files, key)
            for key in chosen
            if key in properties
        }
    if kind == "array":
        return [
            _value(schema.get("items", {}), root, files, name)
            for _ in range(max(1, schema.get("minItems", 0)))
        ]
    if kind == "integer":
        if "minimum" in schema:
            lowest = schema["minimum"]
        else:
            lowest = schema.get("exclusiveMinimum", -1) + 1
        return min(max(lowest, 0), schema.get("maximum", max(lowest, 0)))
    if kind == "number":
        number = max(schema.get("minimum", 0), 1)
        return float(min(number, schema.get("maximum", number)))
    if kind == "boolean":
        return False
    if kind == "string":
        return _string(name, schema, files)
    return None


def _plan(files: _Files, steps: list[dict[str, Any]], **target: Any) -> dict[str, Any]:
    return {"source_sprite_file": str(files.source), **target, "steps": steps}


# The schema walk cannot see a relation between two fields, for example a Frame
# range or a Palette that must contain its transparent index.
_REQUEST_CHANGES: Mapping[str, Callable[[dict[str, Any], _Files], None]] = {
    "cel set": lambda request, _files: request.update(opacity=255),
    "motion apply": lambda request, _files: request.update(
        from_frame=1,
        to_frame=2,
        opacity={
            "interpolation": "step",
            "rounding": "floor",
            "keys": [
                {"frame_number": 1, "opacity": 255},
                {"frame_number": 2, "opacity": 255},
            ],
        },
    ),
    "filter hue-saturation": lambda request, _files: request.update(
        adjustment={"mode": "hsl-multiply", "hue": 0, "saturation": 0, "lightness": 0}
    ),
    "palette reorder": lambda request, _files: request.update(scope="sprite"),
    "raster prepare": lambda request, _files: request["specification"].update(
        palette={
            "entries": [
                {"red": 0, "green": 0, "blue": 0, "alpha": 0},
                {"red": 1, "green": 1, "blue": 1, "alpha": 255},
            ],
            "transparent_index": 0,
        }
    ),
    "export gif": lambda request, files: request["destination"].update(
        path=str(files.directory / "out.gif")
    ),
    "export sheet": lambda request, _files: request.update(filename_format="f{frame1}"),
    "animation compare": lambda request, _files: request.update(
        earlier_frame=1, later_frame=2
    ),
    "animation preview": lambda request, _files: request.update(
        earlier_frame=1, later_frame=2
    ),
    "plan run": lambda request, files: request.update(
        plan=_plan(
            files,
            [
                {
                    "operation": "frame add",
                    "input": {"frame_number": 1, "duration_ms": 100},
                }
            ],
            target_sprite_file=str(files.target),
            in_place=False,
            overwrite=False,
        )
    ),
    "plan check": lambda request, files: request.update(
        plan=_plan(
            files,
            [{"operation": "sprite get", "input": {"inspection_scope": ["frames"]}}],
        )
    ),
}


def minimal_request(command: str, directory: Path) -> dict[str, Any]:
    """Build one schema-valid request for `command` and write its input files.

    The Source Sprite file exists but is not a Sprite: each rule refuses the request
    before Aseprite reads it.
    """
    files = _Files(directory)
    files.source.write_bytes(b"not a Sprite")
    schema = _schema(command).request_schema
    request = _value(schema, schema, files)
    request.pop("aseprite", None)
    request.pop("timeout_seconds", None)
    change = _REQUEST_CHANGES.get(command)
    if change is not None:
        change(request, files)
    return request


SOURCE_FIELDS = ("source_sprite_file", "sprite_file")


def source_location(command: str) -> list[str] | None:
    """Return the request location of the Source Sprite, or None."""
    properties = _schema(command).request_schema["properties"]
    if "plan" in properties:
        return ["plan", "source_sprite_file"]
    for name in SOURCE_FIELDS:
        if name in properties:
            return [name]
    return None


# Rule tables ---------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """One rule that each command of a set obeys, with literal expectations."""

    name: str
    applies: Callable[[OperationDescriptor[Any, Any]], bool]
    expected: tuple[int, str, str]
    run: Callable[[str, Path], Outcome]
    check: Callable[[str, Outcome], None] | None = None
    exempt: Mapping[str, str] = field(default_factory=dict)

    def commands(self) -> list[str]:
        return sorted(
            descriptor.name
            for descriptor in OPERATIONS
            if self.applies(descriptor) and descriptor.name not in self.exempt
        )


def rows(rules: Sequence[Rule]) -> list[Any]:
    return [
        pytest.param(rule, command, id=f"{rule.name}[{command}]")
        for rule in rules
        for command in rule.commands()
    ]


def check_row(rule: Rule, command: str, directory: Path) -> None:
    outcome = rule.run(command, directory)
    assert outcome.result == rule.expected, outcome.envelope
    assert outcome.envelope["operation"] == f"spa {command}"
    validate_failure(command, outcome.envelope)
    # No row starts an Aseprite process, so no row has an exit status.
    assert outcome.envelope["diagnostics"]["exit_status"] is None, outcome.envelope
    if rule.check is not None:
        rule.check(command, outcome)


def check_exemptions(rule: Rule) -> None:
    """Fail on an exemption outside the set of the rule, or without a reason."""
    for command, reason in rule.exempt.items():
        descriptor = DESCRIPTORS.get(command)
        assert descriptor is not None and rule.applies(descriptor), (rule.name, command)
        assert reason.strip(), (rule.name, command)
