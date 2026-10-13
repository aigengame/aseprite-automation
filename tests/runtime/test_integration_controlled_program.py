"""Prove controlled producers directly before using SPA's native transport."""

import subprocess
from pathlib import Path

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
