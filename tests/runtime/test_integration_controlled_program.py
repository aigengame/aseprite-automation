"""Prove controlled producers directly before using SPA's native transport."""

import json
import os
import subprocess
from pathlib import Path

from tests.console_program import console_program
from tests.script.support import script_runtime
from tests.support import fake_probe_response


def test_controlled_probe_preserves_exact_request_and_response_bytes(
    tmp_path: Path,
) -> None:
    response = '{"kernel_protocol_version":1,"status":"ok","value":"中文🚀"}'
    binary = fake_probe_response(tmp_path, response)
    request, reply, echo = (
        tmp_path / name for name in ("request.json", "reply.json", "echo.json")
    )
    original = '{"nullable":null,"value":"中文🚀","nested":[true,1]}'.encode()
    request.write_bytes(original)
    run = subprocess.run(
        [
            str(binary),
            "--batch",
            "--script-param",
            f"request={request}",
            "--script-param",
            f"response={reply}",
            "--script-param",
            f"echo={echo}",
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout == run.stderr == b""
    assert echo.read_bytes() == original
    assert reply.read_bytes() == response.encode("utf-8")
    assert (binary.parent.parent / "Resources/data/gui.xml").read_bytes() == b"<gui/>"


def test_script_producer_preserves_source_bytes_and_declared_effect(
    tmp_path: Path,
) -> None:
    binary = script_runtime(
        tmp_path,
        "sys.stdout.buffer.write(Path(sys.argv[-1]).read_bytes())\n"
        "print('caller stderr', file=sys.stderr)\n"
        "Path('effect.bin').write_bytes(b'after-run')\nsys.exit(7)",
    )
    script = tmp_path / "caller.lua"
    original = "-- \ufeff 中文🚀\r\nprint('unchanged')\n".encode("utf-8")
    script.write_bytes(original)
    run = subprocess.run(
        [str(binary), "--batch", "--script", str(script)],
        cwd=tmp_path,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert run.returncode == 7, run.stderr
    assert run.stdout == original
    assert run.stderr == b"caller stderr\n"
    assert (tmp_path / "effect.bin").read_bytes() == b"after-run"


def test_console_cli_preserves_launch_identity_and_literal_argv(tmp_path: Path) -> None:
    binary = console_program(
        tmp_path,
        "import json, sys\nsys.stdout.write(json.dumps(sys.argv, ensure_ascii=False))",
        name="spa",
    )
    payload = '{"中文🚀":"%SPA_TEST_LITERAL_VALUE% $SPA_TEST_LITERAL_VALUE"}'
    run = subprocess.run(
        [str(binary), "--input-json", payload],
        env=os.environ | {"SPA_TEST_LITERAL_VALUE": "expanded"},
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert run.stderr == b""
    assert json.loads(run.stdout.decode("utf-8")) == [
        str(binary),
        "--input-json",
        payload,
    ]
