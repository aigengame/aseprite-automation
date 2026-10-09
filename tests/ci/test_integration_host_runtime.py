"""Exercise the private runtime action's executable and scripting boundary."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ACTION = (
    Path(__file__).resolve().parents[2] / ".github/actions/aseprite-runtime/action.yml"
)


@pytest.mark.parametrize("runtime", ["missing", "version-only", "script", "crash"])
def test_host_runtime_requires_a_working_batch_script(tmp_path: Path, runtime) -> None:
    executable = tmp_path / "aseprite"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import sys\nfrom pathlib import Path\n"
        "if '--version' in sys.argv:\n"
        "    print('Aseprite test runtime')\n"
        "    sys.exit(0)\n"
        + (
            "output = next(a.removeprefix('output=') for a in sys.argv if a.startswith('output='))\n"
            "Path(output).write_text('spa-aseprite-script-ok\\n')\n"
            if runtime == "script"
            else f"sys.exit({1 if runtime == 'crash' else 0})\n"
        )
    )
    executable.chmod(0o755)
    env = {
        **os.environ,
        "SPA_TEST_ASEPRITE": str(executable) if runtime != "missing" else "",
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        "DISPLAY": "",
        "WAYLAND_DISPLAY": "",
    }
    body = textwrap.dedent(ACTION.read_text().split("      run: |\n", 1)[1])
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", body],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert (result.returncode == 0) == (runtime == "script"), result.stderr
    if runtime == "script":
        assert f"executable={executable}" in (tmp_path / "outputs").read_text()
    else:
        assert not (tmp_path / "outputs").exists()
    assert not list(tmp_path.glob("spa-aseprite-probe.*"))
