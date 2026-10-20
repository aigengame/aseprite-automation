"""The shared native invocation module checks each envelope with its own schema,
and stops a Lua fixture at its deadline."""

import json
import os
import subprocess
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from tests import native_invocation
from tests.native_invocation import expect_success, run, run_lua, validate_envelope
from tests.support import controlled_runtime, fake_aseprite

MISSING = "/missing/aseprite"


def test_aseprite_comes_from_the_caller_or_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPA_TEST_ASEPRITE", "/missing/from-environment")
    request = {"sprite_file": "/missing/source.aseprite"}

    default = run("frame list", request)
    given = run("frame list", request, aseprite=MISSING, transport="stdin")

    assert request == {"sprite_file": "/missing/source.aseprite"}
    assert default.returncode == given.returncode == 1
    assert default.envelope["details"]["requested_path"] == "/missing/from-environment"
    assert given.envelope["details"]["requested_path"] == MISSING
    assert run("version", {}).envelope["status"] == "success"


def _extra_field(envelope: dict[str, Any]) -> dict[str, Any]:
    return {**envelope, "unexpected": True}


def _without(field: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    return lambda envelope: {k: v for k, v in envelope.items() if k != field}


def _unregistered_code(envelope: dict[str, Any]) -> dict[str, Any]:
    return {**envelope, "code": "unregistered_failure_code"}


@pytest.mark.parametrize(
    ("command", "request_", "change"),
    [
        ("version", {}, _extra_field),
        ("version", {}, _without("spa_version")),
        ("frame list", {"sprite_file": "/missing/source.aseprite"}, _extra_field),
        ("frame list", {"sprite_file": "/missing/source.aseprite"}, _without("code")),
        ("frame list", {"sprite_file": "/missing/source.aseprite"}, _unregistered_code),
        ("frame nosuch", {}, _extra_field),
        ("frame nosuch", {}, _without("code")),
        ("frame nosuch", {}, _unregistered_code),
    ],
    ids=[
        "success-extra-field",
        "success-missing-field",
        "failure-extra-field",
        "failure-missing-field",
        "failure-unregistered-code",
        "access-extra-field",
        "access-missing-field",
        "access-unregistered-code",
    ],
)
def test_changed_envelope_fails_its_own_schema(
    command: str,
    request_: dict[str, Any],
    change: Callable[[dict[str, Any]], dict[str, Any]],
) -> None:
    envelope = run(command, request_, aseprite=MISSING).envelope

    with pytest.raises(ValidationError):
        validate_envelope(command, change(envelope))


@pytest.mark.parametrize(
    ("command", "change", "error", "status"),
    [
        ("version", lambda stdout: "", AssertionError, 0),
        ("version", lambda stdout: "not json", AssertionError, 0),
        ("version", lambda stdout: "[]", ValidationError, 0),
        (
            "version",
            lambda stdout: json.dumps({**json.loads(stdout), "unexpected": True}),
            ValidationError,
            0,
        ),
        ("frame nosuch", lambda stdout: "[]", ValidationError, 2),
    ],
    ids=[
        "empty-stdout",
        "not-json",
        "not-an-object",
        "invalid-envelope",
        "access-not-an-object",
    ],
)
def test_run_refuses_bad_stdout_with_process_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    change: Callable[[str], str],
    error: type[Exception],
    status: int,
) -> None:
    installed = native_invocation.spa

    def changed_spa(
        *args: str, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        process = installed(*args, stdin=stdin)
        return subprocess.CompletedProcess(
            process.args, process.returncode, change(process.stdout), process.stderr
        )

    monkeypatch.setattr(native_invocation, "spa", changed_spa)

    with pytest.raises(error) as failure:
        run(command, {})

    message = "".join(traceback.format_exception_only(failure.value))
    assert f"exit status: {status}" in message


def test_expect_success_refuses_a_failure_envelope_with_process_diagnostics() -> None:
    with pytest.raises(AssertionError, match="exit status: 1"):
        expect_success(
            "frame list", {"sprite_file": "/missing/source.aseprite"}, aseprite=MISSING
        )


@pytest.mark.skipif(os.name != "posix", reason="signal 0 checks the process on POSIX")
def test_run_lua_stops_a_fixture_at_the_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = tmp_path / "pid"
    binary = fake_aseprite(
        tmp_path,
        f'echo $$ > "{pid}"\necho started\necho waiting >&2\nexec sleep 30\n',
    )
    monkeypatch.setattr(native_invocation, "LUA_FIXTURE_DEADLINE_SECONDS", 2)
    script = tmp_path / "hang.lua"

    with pytest.raises(AssertionError) as failure:
        run_lua(script, controlled_runtime(binary), target="out.aseprite", flag=True)

    message = str(failure.value)
    assert f"did not exit in 2 s: {script}" in message
    assert "parameters: target=out.aseprite flag=true" in message
    assert "stdout:\nstarted\n" in message
    assert "stderr:\nwaiting\n" in message
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid.read_text()), 0)
