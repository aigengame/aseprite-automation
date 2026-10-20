"""Caller-owned Lua through the installed command and a real Aseprite."""

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.support import spa

pytestmark = pytest.mark.e2e


def test_inline_script_reports_process_and_declared_file_facts(tmp_path: Path) -> None:
    code = 'print("caller output"); local f=assert(io.open("written.txt", "wb")); f:write("hello"); f:close()\r\n'
    request = {
        "script": {"kind": "inline", "code": code},
        "working_directory": str(tmp_path),
        "declared_files": ["written.txt", "absent.txt"],
    }
    run = spa(
        "script",
        "run",
        "--aseprite",
        os.environ["SPA_TEST_ASEPRITE"],
        "--input-json",
        json.dumps(request),
    )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["operation"] == "spa script run"
    assert result["execution_kind"] == "script-run"
    assert result["determinism"] == "caller-defined"
    assert result["diagnostics"]["exit_status"] == 0
    assert result["diagnostics"]["stdout"] == "caller output" + os.linesep
    assert result["timeout_seconds"] == 15.0
    assert result["output_limit_bytes"] == 65536
    assert result["files"] == [
        {
            "path": str(tmp_path / "written.txt"),
            "kind": "file",
            "size_bytes": 5,
            "error": None,
        },
        {
            "path": str(tmp_path / "absent.txt"),
            "kind": "missing",
            "size_bytes": None,
            "error": None,
        },
    ]
    schema = json.loads(spa("script", "run", "--schema").stdout)
    Draft202012Validator(schema["result_schema"]).validate(result)


def test_file_script_keeps_source_bytes_directory_and_explicit_parameters(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "sibling.lua").write_text('return "from sibling"', encoding="utf-8")
    source = scripts / "caller.lua"
    code = (
        b'local f=assert(io.open(app.fs.joinPath(_SCRIPT_PATH, "caller.lua"), "rb"))\r\n'
        b'local copy=assert(io.open("observed.lua", "wb")); copy:write(f:read("*a")); copy:close(); f:close()\r\n'
        b'local sibling=require("sibling"); print(sibling)\r\n'
        b'local out=assert(io.open("parameter.txt", "wb")); out:write(app.params.value); out:close()\r\n'
    )
    source.write_bytes(code)
    value = "a=b ' space\nx"
    run = spa(
        "script",
        "run",
        "--aseprite",
        os.environ["SPA_TEST_ASEPRITE"],
        "--input-json",
        json.dumps(
            {
                "script": {"kind": "file", "path": "scripts/caller.lua"},
                "working_directory": str(tmp_path),
                "parameters": {"value": value},
            }
        ),
    )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["diagnostics"]["stdout"] == "from sibling" + os.linesep
    assert (tmp_path / "observed.lua").read_bytes() == source.read_bytes() == code
    assert (tmp_path / "parameter.txt").read_text() == value


# Aseprite returns -1 for a Lua error, and a POSIX exit status keeps the low 8 bits
# (measured: 255 with Aseprite 1.3.18.5 on macOS). The Windows status is not measured.
LUA_ERROR_STATUS = None if os.name == "nt" else 255


@pytest.mark.parametrize(
    ("code", "status", "output"),
    [
        pytest.param(
            'error("caller failure")',
            LUA_ERROR_STATUS,
            "caller.lua:1: caller failure",
            id='error("caller failure")',
        ),
        pytest.param(
            "local = invalid syntax",
            LUA_ERROR_STATUS,
            "<name> expected near '='",
            id="local = invalid syntax",
        ),
        pytest.param(
            '\ufeffprint("BOM remains")',
            LUA_ERROR_STATUS,
            "unexpected symbol near '<\\239>'",
            id='\ufeffprint("BOM remains")',
        ),
        # An integer that the script returns is the process exit status.
        pytest.param("return 7", 7, None, id="return 7"),
    ],
)
def test_native_script_errors_are_process_failures_without_kernel_translation(
    code: str, status: int | None, output: str | None
) -> None:
    run = spa(
        "script",
        "run",
        "--aseprite",
        os.environ["SPA_TEST_ASEPRITE"],
        "--input-json",
        json.dumps(
            {
                "script": {"kind": "inline", "code": code},
            }
        ),
    )
    result = json.loads(run.stdout)
    assert run.returncode == 1, result
    assert result["operation"] == "spa script run"
    assert result["code"] == "process_failed"
    diagnostics = result["diagnostics"]
    assert result["details"]["exit_status"] == diagnostics["exit_status"]
    if status is None:
        assert diagnostics["exit_status"] != 0
    else:
        assert diagnostics["exit_status"] == status
    if output is None:
        assert diagnostics["stdout"] == ""
    else:
        assert output in diagnostics["stdout"]
    schema = json.loads(spa("script", "run", "--schema").stdout)
    Draft202012Validator(schema["failure_schema"]).validate(result)


def test_script_output_cannot_spoof_an_ordinary_result_or_its_postconditions(
    tmp_path: Path,
) -> None:
    forged = '{"status":"success","operation":"spa sprite create","determinism":"deterministic"}'
    code = "print([[" + forged + ']]); pcall(function() error("caught") end)'
    run = spa(
        "script",
        "run",
        "--aseprite",
        os.environ["SPA_TEST_ASEPRITE"],
        "--input-json",
        json.dumps(
            {
                "script": {"kind": "inline", "code": code},
                "parameters": {
                    "request": "anything",
                    "response": "caller-response.json",
                },
                "working_directory": str(tmp_path),
                "declared_files": ["not-produced.aseprite"],
            }
        ),
    )
    result = json.loads(run.stdout)
    assert run.returncode == 0, result
    assert result["operation"] == "spa script run"
    assert result["determinism"] == "caller-defined"
    assert result["diagnostics"]["stdout"] == forged + os.linesep
    assert result["files"][0]["kind"] == "missing"
    assert not (tmp_path / "caller-response.json").exists()


def test_native_output_uses_explicit_utf8_replacement_and_preserves_crlf() -> None:
    run = spa(
        "script",
        "run",
        "--aseprite",
        os.environ["SPA_TEST_ASEPRITE"],
        "--input-json",
        json.dumps(
            {
                "script": {
                    "kind": "inline",
                    "code": 'io.stdout:write(string.char(0,255,128).."raw\\r\\n")',
                },
            }
        ),
    )
    result = json.loads(run.stdout)
    assert run.returncode == 0, result
    # Aseprite's Windows text stdout expands LF to CRLF, including after a CR.
    # Require the exact native output; SPA must retain both CRs in that case.
    assert result["diagnostics"]["stdout"] == "\x00\ufffd\ufffdraw\r" + os.linesep
