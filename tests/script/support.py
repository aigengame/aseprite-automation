"""Controlled native process boundary for script transport tests."""

import json
import os
import shlex
import sys
from pathlib import Path

from tests.support import fake_aseprite, python_aseprite


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
    if os.name == "nt":
        return python_aseprite(
            tmp_path,
            "if any(Path(arg).name == 'probe.lua' for arg in sys.argv[1:]):\n"
            "    Path(arguments['echo']).write_bytes(Path(arguments['request']).read_bytes())\n"
            f"    Path(arguments['response']).write_text({json.dumps(probe)!r}, encoding='utf-8')\n"
            "else:\n" + "\n".join("    " + line for line in body.splitlines()) + "\n",
        )
    driver.write_text(
        "import os, sys, time\nfrom pathlib import Path\n" + body + "\n",
        encoding="utf-8",
    )
    # Keep the protocol stub independent of Python startup. The caller process
    # can still time out before it produces any output.
    return fake_aseprite(
        tmp_path,
        f"""probe_request=
probe_response=
probe_echo=
is_probe=false
for argument in "$@"; do
  case "$argument" in
    request=*) probe_request=${{argument#request=}};;
    response=*) probe_response=${{argument#response=}};;
    echo=*) probe_echo=${{argument#echo=}};;
    */probe.lua) is_probe=true;;
  esac
done
if [ "$is_probe" = true ]; then
  cp "$probe_request" "$probe_echo"
  printf '%s' {shlex.quote(json.dumps(probe))} > "$probe_response"
else
  exec {shlex.quote(sys.executable)} {shlex.quote(str(driver))} "$@"
fi
""",
    )
