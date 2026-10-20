"""Validate the controlled Aseprite entries independently of SPA's pipe capture."""

import json
import subprocess

import pytest

from tests.script.support import script_runtime
from tests.support import (
    PROBE_ONLY_REFUSAL,
    fake_probe_response,
    probe_only_aseprite,
    process_diagnostics,
    python_aseprite,
    spa,
)


@pytest.mark.parametrize("status", [0, 13])
def test_python_entry_preserves_arguments_streams_and_file_effects(tmp_path, status):
    binary = python_aseprite(
        tmp_path,
        "import json\n"
        "Path('arguments.json').write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
        "sys.stdout.buffer.write(b'output\\r\\n')\n"
        "sys.stderr.buffer.write(b'diagnostic\\n')\n"
        f"sys.exit({status})",
    )
    arguments = ["a b", 'literal"quote', "response=a=b", "", "tail\\"]
    run = subprocess.run(
        [str(binary), *arguments],
        cwd=tmp_path,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert run.returncode == status, process_diagnostics(run)
    assert run.stdout == b"output\r\n", process_diagnostics(run)
    assert run.stderr == b"diagnostic\n", process_diagnostics(run)
    assert (
        json.loads((tmp_path / "arguments.json").read_text(encoding="utf-8"))
        == arguments
    )


def test_probe_fixture_copies_request_bytes_and_response(tmp_path):
    response = '{"status":"ok","message":"响应"}'
    binary = fake_probe_response(tmp_path, response)
    request, echo, result = (tmp_path / name for name in ("request", "echo", "result"))
    request.write_bytes(b'{"echo":"\xe5\x80\xbc"}\r\n')
    run = subprocess.run(
        [str(binary), f"request={request}", f"echo={echo}", f"response={result}"],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert (run.returncode, run.stdout, run.stderr) == (0, b"", b""), (
        process_diagnostics(run)
    )
    assert echo.read_bytes() == request.read_bytes()
    assert result.read_bytes() == response.encode("utf-8")


def test_probe_only_fixture_answers_the_probe_and_refuses_other_calls(tmp_path):
    binary = probe_only_aseprite(tmp_path, ["aseprite_runtime_introspection"])
    info = spa("info", "--aseprite", str(binary), "--json")
    assert info.returncode == 0, process_diagnostics(info)
    runtime = json.loads(info.stdout)["runtime"]
    assert runtime["verified_capabilities"] == ["aseprite_runtime_introspection"]
    request, result = tmp_path / "request", tmp_path / "result"
    request.write_bytes(b"{}")
    kernel = subprocess.run(
        [str(binary), f"request={request}", f"response={result}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert (kernel.returncode, kernel.stdout) == (97, ""), process_diagnostics(kernel)
    assert kernel.stderr.strip() == PROBE_ONLY_REFUSAL
    assert not result.exists()


def test_script_fixture_keeps_probe_separate_from_caller(tmp_path):
    binary = script_runtime(
        tmp_path,
        "Path('effect').write_bytes(Path(sys.argv[-1]).read_bytes()); sys.exit(7)",
    )
    request, echo, result = (tmp_path / name for name in ("request", "echo", "result"))
    request.write_bytes(b'{"echo":null}\r\n')
    probe = subprocess.run(
        [
            str(binary),
            f"request={request}",
            f"echo={echo}",
            f"response={result}",
            "--script",
            str(tmp_path / "probe.lua"),
        ],
        cwd=tmp_path,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert (probe.returncode, probe.stdout, probe.stderr) == (0, b"", b""), (
        process_diagnostics(probe)
    )
    assert echo.read_bytes() == request.read_bytes()
    assert json.loads(result.read_text(encoding="utf-8"))["api_version"] == 41
    assert not (tmp_path / "effect").exists()
    source = tmp_path / "caller.lua"
    source.write_bytes(b"-- exact\r\nreturn 0\n")
    caller = subprocess.run(
        [str(binary), "--script", str(source)],
        cwd=tmp_path,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert (caller.returncode, caller.stdout, caller.stderr) == (7, b"", b""), (
        process_diagnostics(caller)
    )
    assert (tmp_path / "effect").read_bytes() == source.read_bytes()
