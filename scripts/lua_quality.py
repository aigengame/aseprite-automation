"""Check or format every tracked Lua source and test fixture."""

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", nargs="?", choices=("check", "lint", "format"), default="check"
    )
    mode = parser.parse_args().mode

    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "*.lua"], cwd=ROOT
    )
    files = [os.fsdecode(name) for name in tracked.split(b"\0") if name]
    if not files:
        parser.error("no tracked Lua files found")

    failed = False
    if mode in ("check", "lint"):
        failed = (
            subprocess.run(["luacheck", *files], cwd=ROOT, check=False).returncode != 0
        )
    if mode in ("check", "format"):
        command = ["stylua", *files]
        if mode == "check":
            command.insert(1, "--check")
        failed = (
            subprocess.run(command, cwd=ROOT, check=False).returncode != 0 or failed
        )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
