"""Run the selected CLI with explicit JSON requests."""

import asyncio
import json
import os
import signal
from dataclasses import dataclass
from typing import Any


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
    def __init__(self, command: list[str], environment: dict[str, str]):
        self.command = command
        self.environment = environment

    async def invoke(self, operation: str, arguments: dict[str, Any]) -> Outcome:
        command = [
            *self.command,
            *operation.removeprefix("spa ").split(),
            "--input-json",
            "-",
            "--json",
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.environment,
                start_new_session=os.name == "posix",
            )
        except OSError as exc:
            raise AdapterError(
                "Could not start SPA", command=command, reason=str(exc)
            ) from exc
        try:
            stdout, stderr = await process.communicate(json.dumps(arguments).encode())
        finally:
            if process.returncode is None:
                # The native child inherits this group. Cancellation must not orphan it.
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                await process.wait()
        diagnostics: dict[str, Any] = {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "exit_status": process.returncode,
        }
        try:
            payload = json.loads(stdout)
            if not isinstance(payload, dict):
                raise TypeError("Expected a JSON object")
        except (ValueError, TypeError) as exc:
            raise AdapterError(
                "SPA did not return a JSON object", **diagnostics
            ) from exc
        assert process.returncode is not None
        return Outcome(
            payload, diagnostics["stdout"], diagnostics["stderr"], process.returncode
        )
