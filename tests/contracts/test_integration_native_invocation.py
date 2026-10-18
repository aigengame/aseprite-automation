"""The shared native invocation module checks each envelope with its own schema."""

import json
import subprocess
import traceback
from collections.abc import Callable
from typing import Any

import pytest
from jsonschema import ValidationError

from tests import native_invocation
from tests.native_invocation import expect_success, run, validate_envelope

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
    ("change", "error"),
    [
        (lambda stdout: "", AssertionError),
        (lambda stdout: "not json", AssertionError),
        (
            lambda stdout: json.dumps({**json.loads(stdout), "unexpected": True}),
            ValidationError,
        ),
    ],
    ids=["empty-stdout", "not-json", "invalid-envelope"],
)
def test_run_refuses_bad_stdout_with_process_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    change: Callable[[str], str],
    error: type[Exception],
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
        run("version", {})

    assert "exit status: 0" in "".join(traceback.format_exception_only(failure.value))


def test_expect_success_refuses_a_failure_envelope_with_process_diagnostics() -> None:
    with pytest.raises(AssertionError, match="exit status: 1"):
        expect_success(
            "frame list", {"sprite_file": "/missing/source.aseprite"}, aseprite=MISSING
        )
