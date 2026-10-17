"""Controlled native process boundary for script transport tests."""

import json
import shlex
import sys
from pathlib import Path

from tests.support import (
    CONTROLLED_PYTHON_PRELUDE,
    CONTROLLED_SHELL_PRELUDE,
    controlled_aseprite,
)


def script_runtime(tmp_path: Path, body: str) -> Path:
    """Answer the runtime probe, then run body as the caller's script process."""
    probe = json.dumps(
        {
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
    )
    driver = tmp_path / "runtime.py"
    driver.write_text(CONTROLLED_PYTHON_PRELUDE + body + "\n", encoding="utf-8")
    # On POSIX, keep the protocol stub independent of Python startup. The caller
    # process can still time out before it produces any output.
    return controlled_aseprite(
        tmp_path,
        shell=CONTROLLED_SHELL_PRELUDE
        + f"""is_probe=false
for argument in "$@"; do
  case "$argument" in */probe.lua) is_probe=true;; esac
done
if [ "$is_probe" = true ]; then
  cp "$request" "$echo"
  printf '%s' {shlex.quote(probe)} > "$response"
else
  exec {shlex.quote(sys.executable)} {shlex.quote(str(driver))} "$@"
fi
""",
        python="if any(Path(arg).name == 'probe.lua' for arg in sys.argv[1:]):\n"
        "    Path(arguments['echo']).write_bytes(Path(arguments['request']).read_bytes())\n"
        f"    Path(arguments['response']).write_text({probe!r}, encoding='utf-8')\n"
        "else:\n" + "\n".join("    " + line for line in body.splitlines()),
    )
