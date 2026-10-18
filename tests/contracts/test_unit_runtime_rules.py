"""Runtime rules that every command shares, as one table for each rule.

No row starts an Aseprite process. Discovery refuses the Aseprite path of each
discovery row, and the `runtime_incompatible` rows use a probe that reports no
capabilities.
"""

import os
from pathlib import Path

import pytest

from tests.contracts.command_rules import (
    DESCRIPTORS,
    Outcome,
    PortReached,
    Rule,
    check_exemptions,
    check_row,
    minimal_request,
    rows,
    run_request,
    runtime_command,
)

ENVIRONMENT = "environment"
MISSING_EXECUTABLE = "/no/such/aseprite"


def _discovered(command: str, directory: Path, executable: str) -> Outcome:
    request = minimal_request(command, directory)
    return run_request(command, request, "--aseprite", executable, probe="discovering")


def _script(directory: Path, mode: int) -> str:
    # The script has no Aseprite resources beside it.
    executable = directory / "bin" / "aseprite"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(mode)
    return str(executable)


def _not_executable(directory: Path) -> str:
    executable = _script(directory, 0o644)
    if os.access(executable, os.X_OK):
        pytest.skip("the host reports a file without an execute bit as executable")
    return executable


def _requested_path(expected: str):
    def check(_command: str, outcome: Outcome) -> None:
        details = outcome.envelope["details"]
        assert details["requested_path"] == expected, outcome.envelope
        assert details["searched"] == [expected], outcome.envelope

    return check


def _missing_declared_capabilities(command: str, outcome: Outcome) -> None:
    # The result is literal; this compares the details with the Descriptor.
    requirements = DESCRIPTORS[command].runtime_requirements
    assert requirements is not None
    missing = outcome.envelope["details"]["missing_capabilities"]
    assert sorted(missing) == sorted(requirements.required_capabilities)


RULES = (
    Rule(
        "executable_missing",
        runtime_command,
        (1, ENVIRONMENT, "executable_not_found"),
        lambda command, directory: _discovered(command, directory, MISSING_EXECUTABLE),
        _requested_path(MISSING_EXECUTABLE),
    ),
    Rule(
        "executable_not_executable",
        runtime_command,
        (1, ENVIRONMENT, "executable_not_found"),
        lambda command, directory: _discovered(
            command, directory, _not_executable(directory)
        ),
    ),
    Rule(
        "resources_absent",
        runtime_command,
        (1, ENVIRONMENT, "resource_incomplete"),
        lambda command, directory: _discovered(
            command, directory, _script(directory, 0o755)
        ),
    ),
    Rule(
        "runtime_incompatible",
        runtime_command,
        (1, ENVIRONMENT, "runtime_incompatible"),
        lambda command, directory: run_request(
            command, minimal_request(command, directory), probe="incapable"
        ),
        _missing_declared_capabilities,
        exempt={
            "plan run": "checks capabilities inside its direct Kernel invocation",
        },
    ),
)


@pytest.mark.parametrize(("rule", "command"), rows(RULES))
def test_runtime_rule(rule: Rule, command: str, tmp_path: Path) -> None:
    check_row(rule, command, tmp_path)


def test_rule_sets_are_literal_predicates_minus_true_exemptions(
    tmp_path: Path,
) -> None:
    runtime = set(DESCRIPTORS) - {"version", "plan check"}
    assert {
        name for name, descriptor in DESCRIPTORS.items() if runtime_command(descriptor)
    } == runtime
    # A changed predicate or a false exemption removes rows, and fails here.
    assert {rule.name: set(rule.commands()) for rule in RULES} == {
        "executable_missing": runtime,
        "executable_not_executable": runtime,
        "resources_absent": runtime,
        "runtime_incompatible": runtime - {"plan run"},
    }
    # With an incapable probe, `plan run` gets to its direct Kernel invocation.
    with pytest.raises(PortReached, match="invoke_kernel_direct"):
        run_request(
            "plan run", minimal_request("plan run", tmp_path), probe="incapable"
        )
    for rule in RULES:
        check_exemptions(rule)
