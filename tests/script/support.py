"""Controlled native process boundary for script transport tests."""

import json
import shlex
import sys
from pathlib import Path

from tests.support import fake_aseprite


def script_runtime(tmp_path: Path, body: str) -> Path:
    driver = tmp_path / "runtime.py"
    probe = {
        "kernel_protocol_version": 1,
        "status": "ok",
        "aseprite_version": "test",
        "api_version": 41,
        "lua_version": "Lua 5.4",
        "verified_prerequisites": [
            "aseprite_scripting",
            "lua_file_io",
            "aseprite_json",
        ],
        "verified_capabilities": ["aseprite_runtime_introspection"],
    }
    driver.write_text(
        "import json, os, shutil, sys, time\nfrom pathlib import Path\n"
        "if Path(sys.argv[-1]).name == 'probe.lua':\n"
        "    params = dict(arg.split('=', 1) for arg in sys.argv[1:] if '=' in arg)\n"
        "    shutil.copyfile(params['request'], params['echo'])\n"
        f"    Path(params['response']).write_text({json.dumps(probe)!r})\n"
        "else:\n" + "\n".join("    " + line for line in body.splitlines()) + "\n",
        encoding="utf-8",
    )
    return fake_aseprite(
        tmp_path,
        f'exec {shlex.quote(sys.executable)} {shlex.quote(str(driver))} "$@"\n',
    )
