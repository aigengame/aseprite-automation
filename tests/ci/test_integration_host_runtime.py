"""Exercise the private runtime action's executable and scripting boundary."""

import json
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
@pytest.mark.skipif(
    os.name == "nt", reason="Linux provisioning action's POSIX path and Bash probe"
)
def test_host_runtime_requires_a_working_batch_script(tmp_path: Path, runtime) -> None:
    executable = tmp_path / "aseprite"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\nfrom pathlib import Path\n"
        f"with Path({str(tmp_path / 'calls.jsonl')!r}).open('a', encoding='utf-8') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
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
    if runtime == "missing":
        assert "Set SPA_TEST_ASEPRITE" in result.stdout
        assert not (tmp_path / "calls.jsonl").exists()
    else:
        calls = [
            json.loads(line)
            for line in (tmp_path / "calls.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert calls[0] == ["--batch", "--version"]
        assert calls[1][:2] == ["--batch", "--script-param"]
        assert "--script" in calls[1]
    assert not list(tmp_path.glob("spa-aseprite-probe.*"))
