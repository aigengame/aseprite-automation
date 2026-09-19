"""In-process CLI projection tests."""

from typer.main import get_command

from spa.cli import build_app
from spa.descriptors import OPERATIONS


def test_advertised_cli_flags_match_the_actual_typer_commands() -> None:
    def unused_probe(_):
        raise AssertionError("schema inspection must not probe the runtime")

    typer_command = get_command(build_app(unused_probe))
    for descriptor in OPERATIONS:
        actual = {
            parameter.name: parameter.opts[0]
            for parameter in typer_command.commands[descriptor.name].params
        }
        assert actual == descriptor.schema().invocation_schema["x-cli-flags"]
