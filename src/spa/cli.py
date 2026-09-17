"""CLI Access Projection of Operation Descriptors."""

import typer

from spa.application import dispatch
from spa.contracts import (
    FailureEnvelope,
    RequestDetails,
    ValidationIssue,
    failure_envelope,
)
from spa.descriptors import OPERATIONS, OperationDescriptor
from spa.ports import RuntimeProbe


def _emit_failure(failure: FailureEnvelope, human: bool) -> None:
    typer.echo(failure.message if human else failure.model_dump_json())
    raise SystemExit(2 if failure.category == "input" else 1)


def _execute(
    descriptor: OperationDescriptor,
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
    result = dispatch(
        descriptor,
        input_json,
        {"aseprite": aseprite, "timeout_seconds": timeout_seconds},
        probe_runtime,
    )
    if isinstance(result, FailureEnvelope):
        _emit_failure(result, human)
    typer.echo(descriptor.render_human(result) if human else result.model_dump_json())


def _command(descriptor: OperationDescriptor, probe_runtime: RuntimeProbe):
    flags = descriptor.cli_flags
    if descriptor.requires_runtime:

        def runtime_command(
            input_json: str | None = typer.Option(
                None, flags["input_json"], help="Operation Request as a JSON object."
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
                None, flags["input_json"], help="Operation Request as a JSON object."
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
    app = typer.Typer(name="spa", no_args_is_help=True, add_completion=False)
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
            ),
            False,
        )
