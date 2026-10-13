"""Sprite handler transport and public failure classification."""

import json
from pathlib import Path

from jsonschema import validate

from tests.support import controlled_aseprite, spa


def test_handler_error_classification_does_not_parse_human_message(
    tmp_path: Path,
) -> None:
    binary = controlled_aseprite(
        tmp_path,
        """
import sys
from pathlib import Path
parameters = dict(argument.split('=', 1) for argument in sys.argv[1:] if '=' in argument)
if parameters.get('echo'):
    Path(parameters['echo']).write_bytes(Path(parameters['request']).read_bytes())
    response = '{"kernel_protocol_version":1,"status":"ok","aseprite_version":"test","api_version":41,"lua_version":"Lua 5.4","verified_prerequisites":["aseprite_scripting","lua_file_io","aseprite_json"],"verified_capabilities":["aseprite_runtime_introspection","aseprite_sprite_create","aseprite_sprite_inspection"]}'
else:
    response = '{"kernel_protocol_version":1,"status":"error","cause":"operation_rejected","message":"executable not found; malformed response; timeout"}'
Path(parameters['response']).write_text(response, encoding='utf-8')
""",
    )
    target = tmp_path / "never-committed.aseprite"
    run = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(
            {
                "target_sprite_file": str(target),
                "width": 3,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {"kind": "transparent"},
                "overwrite": False,
                "aseprite": str(binary),
            }
        ),
    )
    assert run.returncode == 1, run.stdout
    failure = json.loads(run.stdout)
    validate(
        failure,
        json.loads(spa("sprite", "create", "--schema").stdout)["failure_schema"],
    )
    assert failure["code"] == "kernel_execution_failed"
    assert failure["details"]["reason"] == (
        "executable not found; malformed response; timeout"
    )
    assert not target.exists()
