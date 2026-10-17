"""Ownership step failures keep the original error and still retire the CLI.

These tests replace the platform ownership adapter with a double whose named steps
fail. Cancellation evidence for real owned process trees comes from
test_integration_process.py.
"""

import os
import sys

import anyio
import pytest

from spa.access.mcp.process import StartError, run

# One process: killing a Windows virtual-environment launcher directly would leave
# its interpreter child running.
SLEEPING_CLI = [
    sys._base_executable if sys.platform == "win32" else sys.executable,
    "-c",
    "import time; time.sleep(60)",
]


class FailingOwnership:
    """Own the CLI only after acquisition, and fail the named steps."""

    def __init__(self, *failing: str):
        self.failing = failing
        self.process = None
        self.owned = False
        self.started = anyio.Event()

    def _step(self, name: str) -> None:
        if name in self.failing:
            raise OSError(f"{name} failed")

    def start_options(self):
        return {}

    def acquire(self, process):
        self.process = process
        self.started.set()
        self._step("acquire")
        self.owned = True

    def terminate(self, process):
        self._step("terminate")
        if self.owned:
            process.kill()

    def release(self):
        self._step("release")


async def cancel_after_start(owner: FailingOwnership) -> bool:
    """Cancel the invocation after it starts; return whether run saw cancellation."""
    cancelled = False

    async def invoke():
        nonlocal cancelled
        try:
            await run(SLEEPING_CLI, os.environ.copy(), b"", ownership=lambda: owner)
        except anyio.get_cancelled_exc_class():
            cancelled = True
            raise

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(invoke)
        with anyio.fail_after(5):
            await owner.started.wait()
        tasks.cancel_scope.cancel()
    return cancelled


def test_cancellation_waits_for_cli_when_terminate_fails():
    async def exercise():
        owner = FailingOwnership("terminate")
        assert await cancel_after_start(owner)
        assert owner.process is not None
        assert owner.process.returncode is not None

    anyio.run(exercise)


def test_start_failure_kills_started_cli_when_terminate_fails():
    async def exercise():
        owner = FailingOwnership("acquire", "terminate")
        with pytest.raises(StartError) as raised:
            await run(SLEEPING_CLI, os.environ.copy(), b"", ownership=lambda: owner)
        assert str(raised.value.error) == "acquire failed"
        assert owner.process is not None
        assert owner.process.returncode is not None

    anyio.run(exercise)


def test_start_failure_keeps_original_error_when_release_fails():
    async def exercise():
        owner = FailingOwnership("acquire", "release")
        with pytest.raises(StartError) as raised:
            await run(SLEEPING_CLI, os.environ.copy(), b"", ownership=lambda: owner)
        assert str(raised.value.error) == "acquire failed"
        assert owner.process is not None
        assert owner.process.returncode is not None

    anyio.run(exercise)


def test_cancellation_survives_release_failure():
    async def exercise():
        owner = FailingOwnership("release")
        assert await cancel_after_start(owner)
        assert owner.process is not None
        assert owner.process.returncode is not None

    anyio.run(exercise)
