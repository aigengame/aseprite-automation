"""Smoke test a wheel-installed SPA executable against project metadata."""

import json
import subprocess
import sys
import tomllib
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_installed_cli.py /path/to/spa")

    executable = Path(sys.argv[1])
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    expected_version = metadata["project"]["version"]
    completed = subprocess.run(
        [str(executable), "version"],
        check=True,
        capture_output=True,
        text=True,
    )
    response = json.loads(completed.stdout)
    expected = {
        "status": "success",
        "operation": "spa version",
        "spa_version": expected_version,
    }
    if response != expected:
        raise SystemExit(f"installed CLI returned {response!r}; expected {expected!r}")

    print(f"verified installed SPA {expected_version} at {executable}")


if __name__ == "__main__":
    main()
