"""The shared native invocation module checks each envelope with its own schema."""

from collections.abc import Callable
from typing import Any

import pytest
from jsonschema import ValidationError

from tests.native_invocation import run, validate_envelope

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
