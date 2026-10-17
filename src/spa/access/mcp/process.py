"""Run one MCP CLI invocation and own its complete process tree."""

import asyncio
import contextlib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import anyio

if sys.platform == "win32":
    from ._windows_process import WindowsJob as PlatformOwnership
else:
    from ._posix_process import ProcessGroup as PlatformOwnership


class Ownership(Protocol):
    """Own every process that one CLI invocation starts.

    A step raises OSError when the operating system rejects it.
    """

    def start_options(self) -> dict[str, Any]:
        """Return the subprocess options that start the CLI under ownership."""
        ...

    def acquire(self, process: asyncio.subprocess.Process) -> None:
        """Take ownership of the started CLI and let it run."""
        ...

    def terminate(self, process: asyncio.subprocess.Process) -> None:
        """Stop every owned process."""
        ...

    def release(self) -> None:
        """Give up ownership and leave the owned processes as they are."""
        ...


@dataclass(frozen=True)
class Completion:
    stdout: bytes
    stderr: bytes
    exit_status: int


class StartError(Exception):
    """The selected CLI did not start."""

    def __init__(self, error: OSError):
        super().__init__(str(error))
        self.error = error


async def run(
    command: list[str],
    environment: dict[str, str],
    request: bytes,
    *,
    ownership: Callable[[], Ownership] = PlatformOwnership,
) -> Completion:
    """Send one request to the CLI and return its complete output.

    If the caller cancels before the CLI completes, stop the complete owned
    process tree and wait for it before the cancellation continues.
    """
    try:
        owner = ownership()
        process = await _start(owner, command, environment)
    except OSError as exc:
        raise StartError(exc) from exc
    try:
        stdout, stderr = await process.communicate(request)
    except BaseException:
        try:
            await _retire(owner, process, owned=True)
        finally:
            _release_quietly(owner)
        raise
    owner.release()
    assert process.returncode is not None
    return Completion(stdout, stderr, process.returncode)


async def _retire(
    owner: Ownership, process: asyncio.subprocess.Process, *, owned: bool
) -> None:
    """Stop and wait for the CLI without replacing the error in flight.

    Kill the CLI directly when ownership does not cover it or terminate fails.
    """
    with anyio.CancelScope(shield=True):
        try:
            owner.terminate(process)
        except OSError:
            owned = False
        if not owned and process.returncode is None:
            process.kill()
        await process.wait()


async def _start(
    owner: Ownership, command: list[str], environment: dict[str, str]
) -> asyncio.subprocess.Process:
    try:
        with anyio.CancelScope(shield=True):
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
                **owner.start_options(),
            )
            try:
                owner.acquire(process)
            except BaseException:
                # A failed acquisition can leave the started CLI outside ownership.
                await _retire(owner, process, owned=False)
                raise
    except BaseException:
        _release_quietly(owner)
        raise
    return process


def _release_quietly(owner: Ownership) -> None:
    """Release ownership without replacing the error in flight."""
    with contextlib.suppress(OSError):
        owner.release()
