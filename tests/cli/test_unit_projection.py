"""In-process CLI projection tests."""

from typer.main import get_command

from spa.access.cli import build_app
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import OPERATIONS
from tests.support import operation_services


def test_advertised_cli_flags_match_the_actual_typer_commands() -> None:
    def unused_probe(_):
        raise AssertionError("schema inspection must not probe the runtime")

    typer_command = get_command(
        build_app(operation_services(unused_probe), FAILURE_CODES)
    )
    for descriptor in OPERATIONS:
        path = descriptor.name.split()
        command = typer_command
        for part in path:
            command = command.commands[part]
        actual = {parameter.name: parameter.opts[0] for parameter in command.params}
        assert (
            actual == descriptor.schema(FAILURE_CODES).invocation_schema["x-cli-flags"]
        )
