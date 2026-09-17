"""Installed command surface contract tests."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, validate


def spa(*args: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("spa")
    assert executable, "run tests in the installed project environment"
    return subprocess.run([executable, *args], text=True, capture_output=True)


def test_version_is_an_installed_structured_operation() -> None:
    run = spa("version", "--json")
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["operation"] == "spa version"
    assert result["spa_version"]
    version_schema = json.loads(spa("version", "--schema").stdout)
    Draft202012Validator.check_schema(version_schema["result_schema"])
    Draft202012Validator.check_schema(version_schema["invocation_schema"])
    validate(result, version_schema["result_schema"])


def test_invalid_request_uses_typed_failure_contract() -> None:
    schema = json.loads(spa("version", "--schema").stdout)
    run = spa("version", "--input-json", '{"unexpected": 1}', "--json")
    assert run.returncode == 2
    failure = json.loads(run.stdout)
    validate(failure, schema["failure_schema"])
    assert failure["status"] == "failure"
    assert failure["code"] == "invalid_request"
    assert failure["details"]["kind"] == "invalid_request"
    assert failure["details"]["errors"][0]["location"] == ["unexpected"]


def test_invalid_argv_is_on_the_same_failure_channel() -> None:
    run = spa("info", "--timeout-seconds", "not-a-number")
    assert run.returncode == 2
    assert run.stderr == ""
    failure = json.loads(run.stdout)
    assert failure["code"] == "invalid_request"
    assert failure["details"]["errors"][0]["code"] == "cli_usage"


def test_human_output_projects_the_same_version_result() -> None:
    version = json.loads(spa("version").stdout)["spa_version"]
    run = spa("version", "--human")
    assert run.returncode == 0
    assert run.stdout.strip() == f"SPA {version}"
    assert json.loads(spa("version", "--human", "--json").stdout)["spa_version"] == version


def test_missing_runtime_has_structured_environment_failure() -> None:
    run = spa("info", "--aseprite", "/no/such/aseprite", "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "executable_not_found"
    assert failure["category"] == "environment"
    assert failure["details"]["requested_path"] == "/no/such/aseprite"


def _fake_executable(tmp_path: Path, body: str) -> Path:
    binary = tmp_path / "Aseprite.app" / "Contents" / "MacOS" / "aseprite"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    binary.chmod(0o755)
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    resource.parent.mkdir(parents=True)
    resource.write_text("<gui/>", encoding="utf-8")
    return binary


def test_exit_zero_without_kernel_response_is_failure(tmp_path: Path) -> None:
    binary = _fake_executable(tmp_path, "exit 0\n")
    run = spa("info", "--aseprite", str(binary), "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_missing"
    assert failure["diagnostics"]["exit_status"] == 0


def test_runtime_uses_an_isolated_user_folder(tmp_path: Path) -> None:
    binary = _fake_executable(tmp_path, 'printf "%s" "$ASEPRITE_USER_FOLDER"\nexit 0\n')
    run = spa("info", "--aseprite", str(binary))
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_missing"
    isolated_path = Path(failure["diagnostics"]["stdout"])
    assert isolated_path.name == "aseprite-user"
    assert not isolated_path.exists()


def test_resource_check_is_distinct_from_process_outcome(tmp_path: Path) -> None:
    binary = tmp_path / "aseprite"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    run = spa("info", "--aseprite", str(binary), "--json")
    assert run.returncode == 1
    assert json.loads(run.stdout)["code"] == "resource_incomplete"


def test_timeout_and_output_bound_are_typed(tmp_path: Path) -> None:
    timeout_binary = _fake_executable(tmp_path / "timeout", "exec sleep 3\n")
    timed = spa("info", "--aseprite", str(timeout_binary), "--timeout-seconds", "0.1")
    assert timed.returncode == 1
    assert json.loads(timed.stdout)["code"] == "process_timeout"
    output_binary = _fake_executable(tmp_path / "output", "yes x | head -c 70000\n")
    overflow = spa("info", "--aseprite", str(output_binary))
    assert overflow.returncode == 1
    failure = json.loads(overflow.stdout)
    assert failure["code"] == "output_limit_exceeded"
    assert len(failure["diagnostics"]["stdout"]) <= 65536


@pytest.mark.skipif(not os.environ.get("SPA_TEST_ASEPRITE"), reason="requires installed Aseprite")
def test_info_reports_installed_runtime() -> None:
    run = spa("info", "--aseprite", os.environ["SPA_TEST_ASEPRITE"], "--json")
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["operation"] == "spa info"
    assert result["runtime"]["resource_complete"] is True
    assert result["runtime"]["aseprite_version"]
    assert result["runtime"]["api_version"]
    assert result["supported_capabilities"]
    info_schema = json.loads(spa("info", "--schema").stdout)
    validate(result, info_schema["result_schema"])
    input_run = spa("info", "--input-json", json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"]}))
    assert input_run.returncode == 0, input_run.stdout
    assert json.loads(input_run.stdout)["runtime"] == result["runtime"]


@pytest.mark.skipif(not os.environ.get("SPA_TEST_ASEPRITE"), reason="requires installed Aseprite")
def test_symlinked_executable_resolves_to_resource_complete_bundle(tmp_path: Path) -> None:
    link = tmp_path / "aseprite"
    link.symlink_to(os.environ["SPA_TEST_ASEPRITE"])
    run = spa("info", "--aseprite", str(link))
    assert run.returncode == 0, run.stdout
    runtime = json.loads(run.stdout)["runtime"]
    assert runtime["requested_path"] == str(link)
    assert runtime["discovered_path"] == str(link)
    assert runtime["canonical_path"] == str(Path(os.environ["SPA_TEST_ASEPRITE"]).resolve())


@pytest.mark.skipif(not os.environ.get("SPA_TEST_ASEPRITE"), reason="requires installed Aseprite")
def test_manifest_is_projected_from_command_descriptors() -> None:
    run = spa("schema", "--aseprite", os.environ["SPA_TEST_ASEPRITE"])
    assert run.returncode == 0, run.stdout
    manifest = json.loads(run.stdout)
    assert [entry["operation"] for entry in manifest["operations"]] == [
        "spa info", "spa version", "spa schema"
    ]
    for entry in manifest["operations"]:
        command = entry["operation"].split()[1]
        assert entry == json.loads(spa(command, "--schema").stdout)
        Draft202012Validator.check_schema(entry["request_schema"])
        Draft202012Validator.check_schema(entry["result_schema"])
        Draft202012Validator.check_schema(entry["failure_schema"])
        Draft202012Validator.check_schema(entry["invocation_schema"])
