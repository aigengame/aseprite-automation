"""CLI Access Projection of Operation Descriptors."""

import sys
from typing import Any

import typer

from spa.application import dispatch
from spa.contracts import (
    FailureEnvelope,
    RequestDetails,
    ValidationIssue,
    failure_envelope,
)
from spa.descriptors import ACCESS_FAILURE_CODES, OPERATIONS, OperationDescriptor
from spa.ports import RuntimeProbe


def _emit_failure(failure: FailureEnvelope, human: bool) -> None:
    typer.echo(failure.message if human else failure.model_dump_json())
    raise SystemExit(2 if failure.category == "input" else 1)


def _execute(
    descriptor: OperationDescriptor[Any, Any],
    input_json: str | None,
    aseprite: str | None,
    timeout_seconds: float | None,
    schema: bool,
    human: bool,
    probe_runtime: RuntimeProbe,
) -> None:
    if schema:
        typer.echo(descriptor.schema().model_dump_json())
        return
    if input_json == "-":
        try:
            input_json = sys.stdin.read()
        except (OSError, UnicodeError) as exc:
            _emit_failure(
                failure_envelope(
                    operation=f"spa {descriptor.name}",
                    code="invalid_request",
                    message="Could not read JSON from stdin",
                    details=RequestDetails(
                        errors=[
                            ValidationIssue(
                                location=["input_json"],
                                code="stdin_read",
                                message=str(exc),
                            )
                        ]
                    ),
                    applicable_codes=descriptor.failure_codes,
                ),
                human,
            )
    result = dispatch(
        descriptor,
        input_json,
        {"aseprite": aseprite, "timeout_seconds": timeout_seconds},
        probe_runtime,
    )
    if isinstance(result, FailureEnvelope):
        _emit_failure(result, human)
    typer.echo(descriptor.render_human(result) if human else result.model_dump_json())


def _command(descriptor: OperationDescriptor[Any, Any], probe_runtime: RuntimeProbe):
    flags = descriptor.cli_flags
    if descriptor.requires_runtime:

        def runtime_command(
            input_json: str | None = typer.Option(
                None,
                flags["input_json"],
                help="Operation Request as JSON text, or '-' to read stdin.",
            ),
            aseprite: str | None = typer.Option(
                None,
                flags["aseprite"],
                help=(
                    "Aseprite executable path; defaults to "
                    "SPA_ASEPRITE_EXECUTABLE, then PATH."
                ),
            ),
            timeout_seconds: float | None = typer.Option(
                None, flags["timeout_seconds"], help="Aseprite process deadline."
            ),
            schema: bool = typer.Option(
                False, flags["schema"], help="Emit this Operation's schema."
            ),
            json_output: bool = typer.Option(
                False, flags["json_output"], help="Emit structured JSON (default)."
            ),
            human: bool = typer.Option(
                False, flags["human"], help="Render the same outcome for a human."
            ),
        ) -> None:
            _execute(
                descriptor,
                input_json,
                aseprite,
                timeout_seconds,
                schema,
                human and not json_output,
                probe_runtime,
            )

        command = runtime_command
    else:

        def pure_command(
            input_json: str | None = typer.Option(
                None,
                flags["input_json"],
                help="Operation Request as JSON text, or '-' to read stdin.",
            ),
            schema: bool = typer.Option(
                False, flags["schema"], help="Emit this Operation's schema."
            ),
            json_output: bool = typer.Option(
                False, flags["json_output"], help="Emit structured JSON (default)."
            ),
            human: bool = typer.Option(
                False, flags["human"], help="Render the same outcome for a human."
            ),
        ) -> None:
            _execute(
                descriptor,
                input_json,
                None,
                None,
                schema,
                human and not json_output,
                probe_runtime,
            )

        command = pure_command
    command.__name__ = descriptor.name
    command.__doc__ = f"Run spa {descriptor.name}."
    return command


def build_app(probe_runtime: RuntimeProbe) -> typer.Typer:
    app = typer.Typer(name="spa", no_args_is_help=False, add_completion=False)
    for operation in OPERATIONS:
        app.command(name=operation.name)(_command(operation, probe_runtime))
    return app


def run_cli(app: typer.Typer) -> None:
    """Installed entry point: keep Click usage errors on the same failure channel."""
    command = typer.main.get_command(app)
    try:
        exit_code = command.main(prog_name="spa", standalone_mode=False)
        if isinstance(exit_code, int):
            raise SystemExit(exit_code)
    except typer.exceptions.TyperException as exc:
        context = getattr(exc, "ctx", None)
        operation = context.command_path if context else "spa"
        if operation == "spa":
            applicable_codes = ACCESS_FAILURE_CODES
        else:
            descriptor = next(
                (item for item in OPERATIONS if operation == f"spa {item.name}"),
                None,
            )
            if descriptor is None:
                raise ValueError(f"Unknown CLI failure path: {operation}") from exc
            applicable_codes = descriptor.failure_codes
        message = exc.format_message() if hasattr(exc, "format_message") else str(exc)
        _emit_failure(
            failure_envelope(
                operation=operation,
                code="invalid_request",
                message="Invalid CLI invocation",
                details=RequestDetails(
                    errors=[
                        ValidationIssue(
                            location=[],
                            code="cli_usage",
                            message=message,
                        )
                    ]
                ),
                applicable_codes=applicable_codes,
            ),
            False,
        )
