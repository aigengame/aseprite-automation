"""Call the selected CLI with explicit JSON requests and map its outcome."""

import json
import sys
from dataclasses import dataclass
from typing import Any

from .process import StartError, run


@dataclass(frozen=True)
class Outcome:
    payload: dict[str, Any]
    stdout: str
    stderr: str
    exit_status: int


class AdapterError(Exception):
    """An adapter diagnostic, never a SPA Failure Envelope."""

    def __init__(self, message: str, **diagnostics: Any):
        super().__init__(message)
        self.diagnostics: dict[str, Any] = {"message": message, **diagnostics}


class Cli:
    """Call one selected CLI for MCP tool requests.

    This adapter builds the command, encodes the request and maps the result. The
    process module starts the CLI and owns its process tree.
    """

    def __init__(self, command: list[str], environment: dict[str, str]):
        self.command = command
        self.environment = environment

    async def invoke(self, operation: str, arguments: dict[str, Any]) -> Outcome:
        """Run one Operation and return its Outcome.

        Raise AdapterError when the CLI does not start or does not return a JSON
        object.
        """
        command = [
            *self.command,
            *operation.removeprefix("spa ").split(),
            "--input-json",
            "-",
            "--json",
        ]
        try:
            completion = await run(
                command, self.environment, json.dumps(arguments).encode()
            )
        except StartError as exc:
            raise AdapterError(
                "Could not start SPA", command=command, reason=str(exc.error)
            ) from exc.error
        diagnostics: dict[str, Any] = {
            "stdout": completion.stdout.decode("utf-8", errors="replace"),
            "stderr": completion.stderr.decode("utf-8", errors="replace"),
            "exit_status": completion.exit_status,
        }
        if diagnostics["stderr"]:
            print(diagnostics["stderr"], file=sys.stderr, end="")
        try:
            payload = json.loads(completion.stdout)
            if not isinstance(payload, dict):
                raise TypeError("Expected a JSON object")
        except (ValueError, TypeError) as exc:
            raise AdapterError(
                "SPA did not return a JSON object", **diagnostics
            ) from exc
        return Outcome(
            payload,
            diagnostics["stdout"],
            diagnostics["stderr"],
            completion.exit_status,
        )
