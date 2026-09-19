"""Aseprite Runtime Integration tests with a controlled fake executable."""

import json
import os
import signal
import sys
from pathlib import Path

import pytest
from jsonschema import validate
from typer.testing import CliRunner

from spa.cli import build_app
from spa.descriptors import OPERATIONS
from spa.runtime.aseprite import probe
from tests.support import fake_aseprite, spa


def test_missing_runtime_has_structured_environment_failure() -> None:
    run = spa("info", "--aseprite", "/no/such/aseprite", "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "executable_not_found"
    assert failure["category"] == "environment"
    assert failure["details"]["requested_path"] == "/no/such/aseprite"


def test_spa_prefixed_executable_environment_selects_runtime(tmp_path: Path) -> None:
    binary = fake_aseprite(tmp_path, 'echo "environment-selected"\nexit 13\n')
    environment = os.environ.copy()
    environment["SPA_ASEPRITE_EXECUTABLE"] = str(binary)
    environment["ASEPRITE_EXECUTABLE"] = "/no/such/aseprite"

    run = spa("info", env=environment)

    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "process_failed"
    assert failure["diagnostics"]["stdout"].strip() == "environment-selected"


def test_unprefixed_executable_environment_is_ignored(tmp_path: Path) -> None:
    binary = fake_aseprite(tmp_path, 'echo "unprefixed-selected"\nexit 13\n')
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


@pytest.mark.parametrize("source", ["argv", "environment"])
def test_unexpandable_executable_path_uses_structured_discovery_failure(
    source: str,
) -> None:
    unresolved = "~spa_nonexistent_agent_91a6a27c/aseprite"
    environment = os.environ.copy()
    arguments = ["info", "--json"]
    if source == "argv":
        arguments.extend(("--aseprite", unresolved))
    else:
        environment["SPA_ASEPRITE_EXECUTABLE"] = unresolved

    run = spa(*arguments, env=environment)

    assert run.returncode == 1
    assert run.stderr == ""
    failure = json.loads(run.stdout)
    schema = json.loads(spa("info", "--schema").stdout)
    validate(failure, schema["failure_schema"])
    assert failure["code"] == "executable_not_found"
    assert failure["details"]["requested_path"] == (
        unresolved if source == "argv" else None
    )
    assert failure["details"]["searched"] == [unresolved]
def test_stdin_json_selects_the_installed_runtime(tmp_path: Path) -> None:
    binary = fake_aseprite(tmp_path, 'echo "stdin-selected"\nexit 13\n')
    run = spa(
        "info",
        "--input-json",
        "-",
        stdin=json.dumps({"aseprite": str(binary)}),
    )
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "process_failed"
    assert failure["diagnostics"]["stdout"].strip() == "stdin-selected"


def _fake_truncated_response_executable(tmp_path: Path, exit_status: int) -> Path:
    return fake_aseprite(
        tmp_path,
        f"""
response=
for argument in "$@"; do
  case "$argument" in response=*) response=${{argument#response=}};; esac
done
printf '{{"kernel_protocol_version":1,' > "$response"
exit {exit_status}
""",
    )


def test_exit_zero_without_kernel_response_is_failure(tmp_path: Path) -> None:
    binary = fake_aseprite(tmp_path, "exit 0\n")
    run = spa("info", "--aseprite", str(binary), "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_missing"
    assert failure["category"] == "kernel_protocol"
    assert failure["details"]["kind"] == "kernel_protocol"
    assert "kernel_protocol_version" not in failure["details"]
    assert failure["diagnostics"]["exit_status"] == 0


def test_process_exit_before_kernel_response_is_execution_failure(
    tmp_path: Path,
) -> None:
    binary = fake_aseprite(tmp_path, 'echo "startup failed" >&2\nexit 13\n')
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
    binary = fake_aseprite(tmp_path, "kill -TERM $$\n")
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


def test_zero_exit_with_truncated_kernel_response_is_kernel_protocol_failure(
    tmp_path: Path,
) -> None:
    binary = _fake_truncated_response_executable(tmp_path, 0)
    run = spa("info", "--aseprite", str(binary), "--json")
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_invalid"
    assert failure["category"] == "kernel_protocol"
    assert failure["details"]["kind"] == "kernel_protocol"
    assert "kernel_protocol_version" not in failure["details"]
    assert failure["diagnostics"]["exit_status"] == 0


@pytest.mark.parametrize("private_version", ["2", "true"])
def test_other_kernel_protocol_version_is_rejected_without_negotiation(
    tmp_path: Path, private_version: str
) -> None:
    binary = fake_aseprite(
        tmp_path,
        """
response=
for argument in "$@"; do
  case "$argument" in response=*) response=${argument#response=};; esac
done
printf '{"kernel_protocol_version":%s,"status":"ok","aseprite_version":"test","api_version":1}' 'PRIVATE_VERSION' > "$response"
""".replace("PRIVATE_VERSION", private_version),
    )
    run = spa("info", "--aseprite", str(binary), "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_invalid"
    assert failure["category"] == "kernel_protocol"
    assert "kernel_protocol_version" not in failure["details"]
    assert "unexpected Kernel Protocol version" in failure["message"]


def test_boolean_api_version_is_a_kernel_protocol_failure(tmp_path: Path) -> None:
    binary = fake_aseprite(
        tmp_path,
        """
request=
response=
echo=
for argument in "$@"; do
  case "$argument" in
    request=*) request=${argument#request=};;
    response=*) response=${argument#response=};;
    echo=*) echo=${argument#echo=};;
  esac
done
cp "$request" "$echo"
printf '{"kernel_protocol_version":1,"status":"ok","aseprite_version":"test","api_version":true}' > "$response"
""",
    )
    run = spa("info", "--aseprite", str(binary), "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_invalid"
    assert failure["category"] == "kernel_protocol"
    assert "Traceback" not in run.stderr


def test_json_echo_rejects_boolean_number_swap(tmp_path: Path) -> None:
    binary = fake_aseprite(
        tmp_path,
        """
response=
echo=
for argument in "$@"; do
  case "$argument" in
    response=*) response=${argument#response=};;
    echo=*) echo=${argument#echo=};;
  esac
done
printf '{"kernel_protocol_version":1,"echo":{"nullable":null,"nested":[{"value":null},[true,null,{"flag":1}]]}}' > "$echo"
printf '{"kernel_protocol_version":1,"status":"ok","aseprite_version":"test","api_version":1}' > "$response"
""",
    )
    run = spa("info", "--aseprite", str(binary), "--json")
    assert run.returncode == 1
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_invalid"
    assert "round-trip changed" in failure["message"]


def test_exit_zero_with_kernel_error_is_execution_failure(tmp_path: Path) -> None:
    binary = fake_aseprite(
        tmp_path,
        """
response=
for argument in "$@"; do
  case "$argument" in response=*) response=${argument#response=};; esac
done
printf '{"kernel_protocol_version":1,"status":"error","message":"semantic failure"}' > "$response"
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
    binary = fake_aseprite(tmp_path, 'printf "%s" "$ASEPRITE_USER_FOLDER"\nexit 0\n')
    run = spa("info", "--aseprite", str(binary))
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_missing"
    isolated_path = Path(failure["diagnostics"]["stdout"])
    assert isolated_path.name == "aseprite-user"
    assert not isolated_path.exists()


def test_isolated_user_folder_is_writable_before_launch(tmp_path: Path) -> None:
    binary = fake_aseprite(
        tmp_path,
        'printf "ready" > "$ASEPRITE_USER_FOLDER/startup-check" || exit 17\n',
    )
    run = spa("info", "--aseprite", str(binary), "--json")
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_missing"
    assert failure["diagnostics"]["exit_status"] == 0


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell fixture")
def test_app_bundle_cli_launch_is_scoped_to_macos(tmp_path: Path) -> None:
    binary = fake_aseprite(
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
    binary = fake_aseprite(tmp_path, "")
    binary.write_text("#!/nonexistent/spa-test-interpreter\n", encoding="utf-8")
    run = spa("info", "--aseprite", str(binary), "--json")
    failure = json.loads(run.stdout)
    assert failure["code"] == "process_start_failed"
    assert failure["details"]["executable"] == str(binary.resolve())
    assert failure["details"]["kind"] == "process_start"
    assert failure["details"]["exit_status"] is None


def _assert_preparation_failure(binary: Path) -> None:
    info = next(descriptor for descriptor in OPERATIONS if descriptor.name == "info")
    run = CliRunner().invoke(build_app(probe), ["info", "--aseprite", str(binary)])
    assert run.exit_code == 1, run.stdout
    assert run.stderr == ""
    failure = json.loads(run.stdout)
    assert failure["code"] == "process_start_failed"
    assert failure["category"] == "execution"
    assert failure["details"]["executable"] == str(binary.resolve())
    assert failure["details"]["kind"] == "process_start"
    assert failure["details"]["exit_status"] is None
    assert failure["diagnostics"]["exit_status"] is None
    validate(failure, info.schema().failure_schema)


def test_unwritable_temporary_workspace_has_typed_start_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = fake_aseprite(tmp_path, "exit 0\n")

    def deny_workspace(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("temporary workspace denied")

    monkeypatch.setattr(
        "spa.runtime.aseprite.tempfile.TemporaryDirectory", deny_workspace
    )
    _assert_preparation_failure(binary)


def test_unwritable_kernel_request_has_typed_start_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = fake_aseprite(tmp_path, "exit 0\n")
    original_write_text = Path.write_text
    denied_requests: list[Path] = []

    def deny_request(path: Path, *args: object, **kwargs: object) -> int:
        if path.name == "request.json":
            denied_requests.append(path)
            raise PermissionError("Kernel request write denied")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", deny_request)
    _assert_preparation_failure(binary)
    assert denied_requests and not denied_requests[0].parent.exists()


def test_unwritable_aseprite_user_folder_has_typed_start_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = fake_aseprite(tmp_path, "exit 0\n")
    original_mkdir = Path.mkdir

    def deny_user_folder(path: Path, *args: object, **kwargs: object) -> None:
        if path.name == "aseprite-user":
            raise PermissionError("Aseprite user folder denied")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", deny_user_folder)
    _assert_preparation_failure(binary)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS bundle launch strategy")
@pytest.mark.parametrize("denied_name", ["aseprite", "data"])
def test_unwritable_bundle_link_has_typed_start_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, denied_name: str
) -> None:
    binary = fake_aseprite(tmp_path, "exit 0\n")
    original_symlink_to = Path.symlink_to

    def deny_launch_link(path: Path, *args: object, **kwargs: object) -> None:
        if path.name == denied_name:
            raise PermissionError(f"bundle {denied_name} link denied")
        original_symlink_to(path, *args, **kwargs)

    monkeypatch.setattr(Path, "symlink_to", deny_launch_link)
    _assert_preparation_failure(binary)


def test_timeout_and_output_bound_are_typed(tmp_path: Path) -> None:
    timeout_binary = fake_aseprite(tmp_path / "timeout", "exec sleep 3\n")
    timed = spa("info", "--aseprite", str(timeout_binary), "--timeout-seconds", "0.1")
    assert timed.returncode == 1
    timed_failure = json.loads(timed.stdout)
    assert timed_failure["code"] == "process_timeout"
    assert timed_failure["details"]["executable"] == str(timeout_binary.resolve())
    output_binary = fake_aseprite(tmp_path / "output", "yes x | head -c 70000\n")
    overflow = spa("info", "--aseprite", str(output_binary))
    assert overflow.returncode == 1
    failure = json.loads(overflow.stdout)
    assert failure["code"] == "output_limit_exceeded"
    assert failure["details"]["executable"] == str(output_binary.resolve())
    assert len(failure["diagnostics"]["stdout"]) <= 65536
