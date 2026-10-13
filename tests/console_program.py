"""Install controlled console programs through the repository's uv toolchain."""

import json
import os
import shutil
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path


def console_program(tmp_path: Path, body: str, name: str = "aseprite") -> Path:
    """Return a real console launcher whose Python body runs in its own process."""
    root = tmp_path / "console-program"
    source = root / "src/spa_test_program"
    source.mkdir(parents=True)
    suffix = ".exe" if os.name == "nt" else ""
    # uv strips the Windows suffix from argv[0]; fixtures retain launcher identity.
    identity = "    sys.argv[0] += '.exe'\n" if suffix else ""
    build = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )["build-system"]
    (root / "pyproject.toml").write_text(
        f"[build-system]\nrequires = {json.dumps(build['requires'])}\n"
        f"build-backend = {json.dumps(build['build-backend'])}\n"
        '[project]\nname = "spa-test-program"\nversion = "0.0.0"\n'
        'requires-python = ">=3.13"\n[project.scripts]\n'
        f'{name} = "spa_test_program:main"\n',
        encoding="utf-8",
    )
    (source / "__init__.py").write_text(
        "def main():\n"
        "    import sys\n"
        + identity
        + "    for stream in (sys.stdin, sys.stdout, sys.stderr):\n"
        "        stream.reconfigure(encoding='utf-8', errors=stream.errors, newline='\\n')\n"
        + textwrap.indent(textwrap.dedent(body), "    ")
        + "\n",
        encoding="utf-8",
    )
    uv = shutil.which("uv")
    assert uv, "controlled console fixtures require the existing uv toolchain"
    environment = root / "env"
    dist = root / "dist"
    commands = [
        [uv, "venv", "--offline", "--python", sys.executable, str(environment)],
        [uv, "build", "--offline", "--wheel", "--out-dir", str(dist), str(root)],
        [
            uv,
            "pip",
            "install",
            "--offline",
            "--no-deps",
            "--python",
            str(environment),
            str(dist / "spa_test_program-0.0.0-py3-none-any.whl"),
        ],
    ]
    for command in commands:
        run = subprocess.run(command, capture_output=True, timeout=30, check=False)
        assert run.returncode == 0, (command, run.stdout, run.stderr)
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    installed = scripts / (name + suffix)
    binary = tmp_path / "Aseprite.app/Contents/MacOS" / installed.name
    binary.parent.mkdir(parents=True)
    shutil.copy2(installed, binary)
    return binary
