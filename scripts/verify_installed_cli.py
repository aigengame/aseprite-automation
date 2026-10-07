"""Verify a wheel-installed CLI and every packaged Kernel resource."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_installed_cli.py /path/to/spa")

    executable = Path(sys.argv[1]).resolve()
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    expected_version = metadata["project"]["version"]
    source_kernel = Path("src/spa/kernel")
    expected_resources = {
        path.relative_to(source_kernel).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in source_kernel.rglob("*")
        if path.suffix in {".lua", ".aseprite", ".icc"}
    }
    if not expected_resources:
        raise SystemExit("source Kernel resource inventory is empty")
    installed_python = executable.parent / (
        "python.exe" if os.name == "nt" else "python"
    )
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="spa-installed-check-") as work:
        completed = subprocess.run(
            [str(executable), "version"],
            cwd=work,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            raise SystemExit(
                f"installed CLI version failed ({completed.returncode}): "
                f"{completed.stdout}{completed.stderr}"
            )
        response = json.loads(completed.stdout)
        expected = {
            "status": "success",
            "operation": "spa version",
            "spa_version": expected_version,
        }
        if response != expected:
            raise SystemExit(
                f"installed CLI returned {response!r}; expected {expected!r}"
            )

        inspected = subprocess.run(
            [
                str(installed_python),
                "-I",
                "-c",
                """import hashlib, json, sys
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path

package = files("spa")
metadata = distribution("aseprite-automation")
origin = json.loads(metadata.read_text("direct_url.json") or "{}")
if origin.get("dir_info", {}).get("editable"):
    raise SystemExit("installed verification requires a wheel, not an editable install")
if sys.prefix == sys.base_prefix or not Path(str(package)).resolve().is_relative_to(Path(sys.prefix).resolve()):
    raise SystemExit("SPA must load from the selected isolated Python environment")
print(f"installed package: {package}; Python: {sys.version.split()[0]}")

def inventory(directory, prefix=""):
    result = {}
    for resource in directory.iterdir():
        name = prefix + resource.name
        if resource.is_dir():
            result.update(inventory(resource, name + "/"))
        elif name.endswith((".lua", ".aseprite", ".icc")):
            payload = resource.read_bytes()
            if not payload or payload.startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise SystemExit(f"empty resource or unresolved LFS pointer: {name}")
            result[name] = hashlib.sha256(payload).hexdigest()
    return result

expected = json.loads(sys.argv[1])
actual = inventory(files("spa.kernel"))
if actual != expected:
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    changed = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])
    raise SystemExit(f"Kernel mismatch: missing={missing}, extra={extra}, changed={changed}")
""",
                json.dumps(expected_resources),
            ],
            cwd=work,
            env=environment,
            check=False,
        )
        if inspected.returncode:
            raise SystemExit(inspected.returncode)

    print(
        f"verified installed SPA {expected_version} and {len(expected_resources)} "
        f"Kernel resources at {executable}"
    )


if __name__ == "__main__":
    main()
