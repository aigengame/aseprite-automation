"""Public request isolation and bounded process failures without a real runtime."""

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.script.support import script_runtime
from tests.support import spa

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX process fixture")


def test_timeout_remains_in_force_after_both_output_streams_close(
    tmp_path: Path,
) -> None:
    binary = script_runtime(
        tmp_path, "os.write(1, b'started'); os.close(1); os.close(2); time.sleep(1.2)"
    )
    run = spa(
        "script",
        "run",
        "--aseprite",
        str(binary),
        "--input-json",
        json.dumps(
            {
                "script": {"kind": "inline", "code": ""},
                "timeout_seconds": 0.8,
            }
        ),
    )
    result = json.loads(run.stdout)
    assert result["diagnostics"]["stdout"] == "started", result
    assert run.returncode == 1, result
    assert result["code"] == "process_timeout", result
    assert result["diagnostics"]["exit_status"] is not None


@pytest.mark.parametrize(
    "body,code,output",
    [
        ("print('before failure'); sys.exit(9)", "process_failed", "before failure\n"),
        ("os.write(1, b'x' * 65537)", "output_limit_exceeded", "x" * 65536),
        ("os.write(1, b'started'); time.sleep(10)", "process_timeout", "started"),
    ],
)
def test_script_process_failures_use_registered_schema_and_keep_diagnostics(
    tmp_path, body, code, output
) -> None:
    binary = script_runtime(tmp_path, body)
    request = {"script": {"kind": "inline", "code": ""}, "timeout_seconds": 0.8}
    run = spa(
        "script", "run", "--aseprite", str(binary), "--input-json", json.dumps(request)
    )
    result = json.loads(run.stdout)
    assert run.returncode == 1, result
    assert result["operation"] == "spa script run"
    assert result["code"] == code
    assert result["diagnostics"]["stdout"] == output
    assert result["details"]["exit_status"] == result["diagnostics"]["exit_status"]
    schema = json.loads(spa("script", "run", "--schema").stdout)
    Draft202012Validator(schema["failure_schema"]).validate(result)


@pytest.mark.parametrize(
    "update",
    [
        {"script": {"kind": "inline", "code": "\ud800"}},
        {"script": {"kind": "file", "path": "bad\x00file"}},
        {"parameters": {"a=b": "value"}},
        {"parameters": {"value": "nul\x00value"}},
        {"working_directory": "bad\x00path"},
        {"declared_files": ["bad\x00path"]},
        {"timeout_seconds": 0},
        {"timeout_seconds": 121},
        {"execution_kind": "mutation"},
        {"determinism": "deterministic"},
        {"operation": "sprite create"},
        {"handler": "sprite_create"},
    ],
)
def test_invalid_request_is_rejected_before_runtime(update) -> None:
    request = {"script": {"kind": "inline", "code": ""}, **update}
    run = spa(
        "script",
        "run",
        "--aseprite",
        "/missing/aseprite",
        "--input-json",
        json.dumps(request),
    )
    result = json.loads(run.stdout)
    assert run.returncode == 2, result
    assert result["code"] == "invalid_request", result
    assert result["diagnostics"]["exit_status"] is None


@pytest.mark.parametrize(
    "source", [{"kind": "file", "path": "missing.lua"}, {"kind": "file", "path": "."}]
)
def test_file_input_requires_an_existing_readable_regular_file(
    tmp_path, source
) -> None:
    binary = script_runtime(tmp_path, "raise AssertionError('caller must not run')")
    run = spa(
        "script",
        "run",
        "--aseprite",
        str(binary),
        "--input-json",
        json.dumps(
            {
                "script": source,
                "working_directory": str(tmp_path),
            }
        ),
    )
    result = json.loads(run.stdout)
    assert run.returncode == 2, result
    assert result["code"] == "invalid_request"
    assert result["details"]["errors"][0]["location"] == ["script", "path"]


def test_inline_materialization_is_exact_utf8_without_wrapper(tmp_path) -> None:
    binary = script_runtime(
        tmp_path, "sys.stdout.buffer.write(Path(sys.argv[-1]).read_bytes())"
    )
    source = "-- \ufeff Unicode test\r\nprint('unchanged')\n"
    run = spa(
        "script",
        "run",
        "--aseprite",
        str(binary),
        "--input-json",
        json.dumps(
            {
                "script": {"kind": "inline", "code": source},
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    assert json.loads(run.stdout)["diagnostics"]["stdout"] == source


@pytest.mark.parametrize("verb", ["check", "run"])
def test_scripts_cannot_enter_operation_plans(tmp_path, verb) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"unchanged Source")
    run = spa(
        "plan",
        verb,
        "--input-json",
        json.dumps(
            {
                "plan": {
                    "source_sprite_file": str(source),
                    "steps": [
                        {
                            "operation": "script run",
                            "input": {
                                "script": {"kind": "inline", "code": "error('not run')"}
                            },
                        }
                    ],
                }
            }
        ),
        env=os.environ | {"SPA_ASEPRITE_EXECUTABLE": "/missing/aseprite"},
    )
    result = json.loads(run.stdout)
    assert run.returncode == 2, result
    assert result["code"] == "invalid_request"
    assert source.read_bytes() == b"unchanged Source"


@pytest.mark.parametrize("extra", ["script", "handler", "execution_kind", "operation"])
def test_ordinary_operation_cannot_accept_a_caller_replacement(extra) -> None:
    run = spa(
        "sprite",
        "create",
        "--aseprite",
        "/missing/aseprite",
        "--input-json",
        json.dumps(
            {
                extra: {"kind": "inline", "code": "return 0"},
            }
        ),
    )
    result = json.loads(run.stdout)
    assert run.returncode == 2, result
    assert result["code"] == "invalid_request"
    assert any(
        error["location"] == [extra] and error["code"] == "extra_forbidden"
        for error in result["details"]["errors"]
    )
