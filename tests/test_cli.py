"""Installed command surface contract tests."""

import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, validate
from typer.main import get_command

from spa.cli import build_app
from spa.descriptors import OPERATIONS


def spa(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("spa")
    assert executable, "run tests in the installed project environment"
    return subprocess.run(
        [executable, *args], text=True, capture_output=True, check=False, env=env
    )


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
    assert (
        json.loads(spa("version", "--human", "--json").stdout)["spa_version"] == version
    )


def test_missing_runtime_has_structured_environment_failure() -> None:
    run = spa("info", "--aseprite", "/no/such/aseprite", "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "executable_not_found"
    assert failure["category"] == "environment"
    assert failure["details"]["requested_path"] == "/no/such/aseprite"


def test_spa_prefixed_executable_environment_selects_runtime(tmp_path: Path) -> None:
    binary = _fake_executable(tmp_path, 'echo "environment-selected"\nexit 13\n')
    environment = os.environ.copy()
    environment["SPA_ASEPRITE_EXECUTABLE"] = str(binary)
    environment["ASEPRITE_EXECUTABLE"] = "/no/such/aseprite"

    run = spa("info", env=environment)

    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "process_failed"
    assert failure["diagnostics"]["stdout"].strip() == "environment-selected"


def test_unprefixed_executable_environment_is_ignored(tmp_path: Path) -> None:
    binary = _fake_executable(tmp_path, 'echo "unprefixed-selected"\nexit 13\n')
    environment = os.environ.copy()
    environment.pop("SPA_ASEPRITE_EXECUTABLE", None)
    environment["ASEPRITE_EXECUTABLE"] = str(binary)
    environment["PATH"] = ""

    run = spa("info", env=environment)

    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "executable_not_found"
    assert failure["details"]["searched"] == [
        "SPA_ASEPRITE_EXECUTABLE",
        "PATH:aseprite",
    ]


def _fake_executable(tmp_path: Path, body: str) -> Path:
    binary = tmp_path / "Aseprite.app" / "Contents" / "MacOS" / "aseprite"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    binary.chmod(0o755)
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    resource.parent.mkdir(parents=True)
    resource.write_text("<gui/>", encoding="utf-8")
    return binary


def _fake_truncated_response_executable(tmp_path: Path, exit_status: int) -> Path:
    return _fake_executable(
        tmp_path,
        f"""
response=
for argument in "$@"; do
  case "$argument" in response=*) response=${{argument#response=}};; esac
done
printf '{{"protocol_version":1,' > "$response"
exit {exit_status}
""",
    )


def test_exit_zero_without_kernel_response_is_failure(tmp_path: Path) -> None:
    binary = _fake_executable(tmp_path, "exit 0\n")
    run = spa("info", "--aseprite", str(binary), "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_missing"
    assert failure["diagnostics"]["exit_status"] == 0


def test_process_exit_before_kernel_response_is_execution_failure(
    tmp_path: Path,
) -> None:
    binary = _fake_executable(tmp_path, 'echo "startup failed" >&2\nexit 13\n')
    run = spa("info", "--aseprite", str(binary), "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "process_failed"
    assert failure["category"] == "execution"
    assert failure["details"]["exit_status"] == 13
    assert "startup failed" in failure["diagnostics"]["stderr"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal fixture")
def test_signal_terminated_process_is_reported_as_process_failure(
    tmp_path: Path,
) -> None:
    binary = _fake_executable(tmp_path, "kill -TERM $$\n")
    run = spa("info", "--aseprite", str(binary), "--json")
    failure = json.loads(run.stdout)
    assert failure["code"] == "process_failed"
    assert failure["details"]["exit_status"] == -signal.SIGTERM
    assert "signal 15" in failure["message"]


def test_nonzero_exit_with_truncated_kernel_response_is_process_failure(
    tmp_path: Path,
) -> None:
    binary = _fake_truncated_response_executable(tmp_path, 13)
    run = spa("info", "--aseprite", str(binary), "--json")
    failure = json.loads(run.stdout)
    assert failure["code"] == "process_failed"
    assert failure["category"] == "execution"
    assert failure["diagnostics"]["exit_status"] == 13


def test_zero_exit_with_truncated_kernel_response_is_protocol_failure(
    tmp_path: Path,
) -> None:
    binary = _fake_truncated_response_executable(tmp_path, 0)
    run = spa("info", "--aseprite", str(binary), "--json")
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_invalid"
    assert failure["category"] == "protocol"
    assert failure["diagnostics"]["exit_status"] == 0


def test_exit_zero_with_kernel_error_is_execution_failure(tmp_path: Path) -> None:
    binary = _fake_executable(
        tmp_path,
        """
response=
for argument in "$@"; do
  case "$argument" in response=*) response=${argument#response=};; esac
done
printf '{"protocol_version":1,"status":"error","message":"semantic failure"}' > "$response"
exit 0
""",
    )
    run = spa("info", "--aseprite", str(binary))
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_execution_failed"
    assert failure["category"] == "execution"
    assert failure["details"]["kind"] == "kernel_execution"
    assert failure["details"]["reason"] == "semantic failure"
    assert failure["diagnostics"]["exit_status"] == 0


def test_runtime_uses_an_isolated_user_folder(tmp_path: Path) -> None:
    binary = _fake_executable(tmp_path, 'printf "%s" "$ASEPRITE_USER_FOLDER"\nexit 0\n')
    run = spa("info", "--aseprite", str(binary))
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_missing"
    isolated_path = Path(failure["diagnostics"]["stdout"])
    assert isolated_path.name == "aseprite-user"
    assert not isolated_path.exists()


def test_isolated_user_folder_is_writable_before_launch(tmp_path: Path) -> None:
    binary = _fake_executable(
        tmp_path,
        'printf "ready" > "$ASEPRITE_USER_FOLDER/startup-check" || exit 17\n',
    )
    run = spa("info", "--aseprite", str(binary), "--json")
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_missing"
    assert failure["diagnostics"]["exit_status"] == 0


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell fixture")
def test_app_bundle_cli_launch_is_scoped_to_macos(tmp_path: Path) -> None:
    binary = _fake_executable(
        tmp_path,
        'printf "%s\\n" "$0"\n'
        'if test -f "$(dirname "$0")/data/gui.xml"; then echo data-present; '
        "else echo data-absent; fi\n",
    )
    run = spa("info", "--aseprite", str(binary), "--json")
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_missing"
    launched_path, data_status = failure["diagnostics"]["stdout"].splitlines()
    if sys.platform == "darwin":
        assert launched_path != str(binary.resolve())
        assert Path(launched_path).name == binary.name
        assert data_status == "data-present"
    else:
        assert launched_path == str(binary.resolve())
        assert data_status == "data-absent"


def test_resource_check_is_distinct_from_process_outcome(tmp_path: Path) -> None:
    binary = tmp_path / "aseprite"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    run = spa("info", "--aseprite", str(binary), "--json")
    assert run.returncode == 1
    assert json.loads(run.stdout)["code"] == "resource_incomplete"


def test_process_start_failure_keeps_installed_executable_identity(
    tmp_path: Path,
) -> None:
    binary = _fake_executable(tmp_path, "")
    binary.write_text("#!/nonexistent/spa-test-interpreter\n", encoding="utf-8")
    run = spa("info", "--aseprite", str(binary), "--json")
    failure = json.loads(run.stdout)
    assert failure["code"] == "process_start_failed"
    assert failure["details"]["executable"] == str(binary.resolve())


def test_timeout_and_output_bound_are_typed(tmp_path: Path) -> None:
    timeout_binary = _fake_executable(tmp_path / "timeout", "exec sleep 3\n")
    timed = spa("info", "--aseprite", str(timeout_binary), "--timeout-seconds", "0.1")
    assert timed.returncode == 1
    timed_failure = json.loads(timed.stdout)
    assert timed_failure["code"] == "process_timeout"
    assert timed_failure["details"]["executable"] == str(timeout_binary.resolve())
    output_binary = _fake_executable(tmp_path / "output", "yes x | head -c 70000\n")
    overflow = spa("info", "--aseprite", str(output_binary))
    assert overflow.returncode == 1
    failure = json.loads(overflow.stdout)
    assert failure["code"] == "output_limit_exceeded"
    assert failure["details"]["executable"] == str(output_binary.resolve())
    assert len(failure["diagnostics"]["stdout"]) <= 65536


@pytest.mark.skipif(
    not os.environ.get("SPA_TEST_ASEPRITE"), reason="requires installed Aseprite"
)
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
    input_run = spa(
        "info",
        "--input-json",
        json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert input_run.returncode == 0, input_run.stdout
    assert json.loads(input_run.stdout)["runtime"] == result["runtime"]


@pytest.mark.skipif(
    not os.environ.get("SPA_TEST_ASEPRITE"), reason="requires installed Aseprite"
)
def test_symlinked_executable_resolves_to_resource_complete_bundle(
    tmp_path: Path,
) -> None:
    link = tmp_path / "aseprite"
    link.symlink_to(os.environ["SPA_TEST_ASEPRITE"])
    run = spa("info", "--aseprite", str(link))
    assert run.returncode == 0, run.stdout
    runtime = json.loads(run.stdout)["runtime"]
    assert runtime["requested_path"] == str(link)
    assert runtime["discovered_path"] == str(link)
    assert runtime["canonical_path"] == str(
        Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    )


@pytest.mark.skipif(
    sys.platform != "darwin"
    or not os.environ.get("SPA_TEST_ASEPRITE")
    or os.environ.get("SPA_TEST_MACOS_AGENT_SANDBOX") != "1",
    reason="requires installed Aseprite in a macOS agent sandbox",
)
def test_macos_agent_sandbox_starts_installed_aseprite_script() -> None:
    executable = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    assert executable.parent.name == "MacOS"
    assert executable.parent.parent.name == "Contents"
    assert executable.parent.parent.parent.suffix == ".app"

    run = spa("info", "--aseprite", str(executable), "--json")
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(result, json.loads(spa("info", "--schema").stdout)["result_schema"])
    assert result["runtime"]["canonical_path"] == str(executable)
    assert result["runtime"]["resource_complete"] is True


@pytest.mark.skipif(
    not os.environ.get("SPA_TEST_ASEPRITE"), reason="requires installed Aseprite"
)
def test_manifest_is_projected_from_command_descriptors() -> None:
    run = spa("schema", "--aseprite", os.environ["SPA_TEST_ASEPRITE"])
    assert run.returncode == 0, run.stdout
    manifest = json.loads(run.stdout)
    assert [entry["operation"] for entry in manifest["operations"]] == [
        "spa info",
        "spa version",
        "spa schema",
    ]
    for entry in manifest["operations"]:
        command = entry["operation"].split()[1]
        assert entry == json.loads(spa(command, "--schema").stdout)
        Draft202012Validator.check_schema(entry["request_schema"])
        Draft202012Validator.check_schema(entry["result_schema"])
        Draft202012Validator.check_schema(entry["failure_schema"])
        Draft202012Validator.check_schema(entry["invocation_schema"])


def test_advertised_cli_flags_match_the_actual_typer_commands() -> None:
    def unused_probe(_):
        raise AssertionError("schema inspection must not probe the runtime")

    typer_command = get_command(build_app(unused_probe))
    for descriptor in OPERATIONS:
        actual = {
            parameter.name: parameter.opts[0]
            for parameter in typer_command.commands[descriptor.name].params
        }
        assert actual == descriptor.schema().invocation_schema["x-cli-flags"]
