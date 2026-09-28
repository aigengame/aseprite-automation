"""Account for verification time separately from a cold Aseprite build."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def verification_remaining() -> tuple[float, str]:
    elapsed = time.monotonic() - float(os.environ["SPA_CI_STARTED_AT"])
    excluded = float(os.environ.get("SPA_ASEPRITE_BUILD_SECONDS", "0"))
    limit = float(os.environ["SPA_CI_BUDGET_SECONDS"])
    if not (0 <= excluded <= elapsed and limit > 0):
        raise ValueError("Invalid CI budget or excluded build time")
    charged = elapsed - excluded
    summary = (
        "### Verification budget\n"
        f"- Elapsed: {elapsed:.1f}s\n"
        f"- Aseprite cold build excluded: {excluded:.1f}s\n"
        f"- Verification charged: {charged:.1f}s; budget: {limit:.1f}s\n"
    )
    return limit - charged, summary


def run_bounded(
    command: list[str], seconds: float, failure: str = "Verification budget exhausted"
) -> int:
    if seconds <= 0:
        print(failure, file=sys.stderr)
        return 124
    with subprocess.Popen(command, start_new_session=True) as process:
        try:
            return process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            print(failure, file=sys.stderr)
            return 124


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in {"run", "build", "check"}:
        raise ValueError("Use ci_budget.py check, run COMMAND, or build COMMAND")
    remaining, summary = verification_remaining()
    if sys.argv[1] == "run":
        return run_bounded(sys.argv[2:], remaining)
    if sys.argv[1] == "build":
        if remaining <= 0:
            print("Verification budget exhausted before cold build", file=sys.stderr)
            return 124
        started = time.monotonic()
        try:
            return run_bounded(
                sys.argv[2:],
                40 * 60,
                "Aseprite cold build exceeded its 40-minute safety limit",
            )
        finally:
            elapsed = time.monotonic() - started
            with Path(os.environ["GITHUB_ENV"]).open("a") as environment:
                environment.write(f"SPA_ASEPRITE_BUILD_SECONDS={elapsed}\n")
            print(f"Aseprite cold build excluded: {elapsed:.1f}s", flush=True)
    print(summary, end="")
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as report:
        report.write(summary)
    return 0 if remaining >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
