"""Bounded reads from Windows process pipes without socket-only selectors."""

import os
import subprocess
import time


def capture(
    process: subprocess.Popen[bytes],
    captured: dict[str, bytearray],
    deadline: float,
    output_limit: int,
) -> tuple[bool, bool]:
    """Read both streams until EOF, the existing deadline, or a stream limit."""
    assert process.stdout is not None and process.stderr is not None
    streams = {"stdout": process.stdout.fileno(), "stderr": process.stderr.fileno()}
    for descriptor in streams.values():
        os.set_blocking(descriptor, False)
    while streams:
        if time.monotonic() >= deadline:
            return True, False
        progressed = False
        for name, descriptor in list(streams.items()):
            try:
                chunk = os.read(descriptor, 8192)
            except BlockingIOError:
                continue
            progressed = True
            if not chunk:
                del streams[name]
                continue
            target = captured[name]
            remaining = output_limit - len(target)
            target.extend(chunk[:remaining])
            if len(chunk) > remaining:
                return False, True
        if not progressed:
            time.sleep(min(0.01, max(0, deadline - time.monotonic())))
    return False, False
