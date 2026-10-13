"""Controlled native process boundary for script transport tests."""

import json
from pathlib import Path

from tests.support import controlled_aseprite


def script_runtime(tmp_path: Path, body: str) -> Path:
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
    return controlled_aseprite(
        tmp_path,
        f"""
import os, sys, time
from pathlib import Path
if Path(sys.argv[-1]).name == 'probe.lua':
    parameters = dict(argument.split('=', 1) for argument in sys.argv[1:] if '=' in argument)
    Path(parameters['echo']).write_bytes(Path(parameters['request']).read_bytes())
    Path(parameters['response']).write_text({json.dumps(probe)!r}, encoding='utf-8')
    return
"""
        + body,
    )
