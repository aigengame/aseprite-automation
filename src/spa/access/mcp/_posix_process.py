"""Own one POSIX MCP CLI invocation and its inherited children."""

import sys

if sys.platform != "win32":
    import asyncio
    import os
    import signal
    from typing import Any

    class ProcessGroup:
        """Start the CLI as a session leader so one signal reaches its group."""

        def start_options(self) -> dict[str, Any]:
            return {"start_new_session": True}

        def acquire(self, process: asyncio.subprocess.Process) -> None:
            """The new session owns the CLI from its start."""

        def terminate(self, process: asyncio.subprocess.Process) -> None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        def release(self) -> None:
            """A process group has no handle to release."""
