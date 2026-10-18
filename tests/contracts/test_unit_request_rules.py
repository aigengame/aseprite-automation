"""Request rules that every command shares, as one table for each rule.

Every row refuses the request before the runtime probe: the rows use a probe that
fails the row when it is called.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from spa.contracts.public import OperationSchema
from tests.contracts.command_rules import (
    DESCRIPTORS,
    INPUT_REFUSAL,
    Outcome,
    Rule,
    check_exemptions,
    check_row,
    every_command,
    minimal_request,
    rows,
    run_request,
    run_spa,
    runtime_command,
    source_location,
)


def _with_input(command: str, text: str) -> Outcome:
    return run_spa([*command.split(), "--input-json", text])


def _without_source(command: str, directory: Path) -> Outcome:
    request = minimal_request(command, directory)
    location = source_location(command)
    assert location is not None, f"{command} has no Source: exempt it with a reason"
    parent = request
    for part in location[:-1]:
        parent = parent[part]
    del parent[location[-1]]
    return run_request(command, request)


def _errors(*expected: tuple[list[Any], str]):
    def check(_command: str, outcome: Outcome) -> None:
        assert outcome.errors == list(expected), outcome.envelope

    return check


def _missing_source_error(command: str, outcome: Outcome) -> None:
    location = source_location(command)
    if location == ["plan", "source_sprite_file"]:
        # A Plan can start from a creation Step instead of a Source Sprite.
        assert outcome.errors == [(["plan"], "value_error")], outcome.envelope
        assert outcome.envelope["details"]["errors"][0]["message"] == (
            "Value error, Plan requires exactly one Source Sprite or first creation Step"
        )
    else:
        assert outcome.errors == [(location, "missing")], outcome.envelope


NO_SOURCE = {
    "info": "reports runtime facts only",
    "version": "reports package facts only",
    "schema": "reports runtime facts only",
    "script run": "runs caller-owned Lua, not a Sprite Operation",
    "sprite create": "creates a Target from nothing",
    "raster prepare": "reads a raster input, not a Sprite",
    "selection create": "transports a Selection value",
    "selection combine": "transports Selection values",
    "selection invert": "transports a Selection value",
    "selection grow": "transports a Selection value",
    "selection shrink": "transports a Selection value",
    "selection transform": "transports a Selection value",
    "selection validate": "transports a Selection value",
    "selection export": "transports a Selection value",
    "selection preview": "transports a Selection value",
}

RULES = (
    Rule(
        "malformed_json",
        every_command,
        INPUT_REFUSAL,
        lambda command, _directory: _with_input(command, "{"),
        _errors(([], "json_input")),
    ),
    Rule(
        "non_object_json",
        every_command,
        INPUT_REFUSAL,
        lambda command, _directory: _with_input(command, "[]"),
        _errors(([], "json_input")),
    ),
    Rule(
        "unknown_field",
        every_command,
        INPUT_REFUSAL,
        lambda command, directory: run_request(
            command, {**minimal_request(command, directory), "zz_unknown": 1}
        ),
        _errors((["zz_unknown"], "extra_forbidden")),
    ),
    Rule(
        "timeout_zero",
        runtime_command,
        INPUT_REFUSAL,
        lambda command, directory: run_request(
            command, {**minimal_request(command, directory), "timeout_seconds": 0}
        ),
        _errors((["timeout_seconds"], "greater_than")),
    ),
    Rule(
        "timeout_above_limit",
        runtime_command,
        INPUT_REFUSAL,
        lambda command, directory: run_request(
            command, {**minimal_request(command, directory), "timeout_seconds": 121}
        ),
        _errors((["timeout_seconds"], "less_than_equal")),
    ),
    Rule(
        "missing_source",
        every_command,
        INPUT_REFUSAL,
        _without_source,
        _missing_source_error,
        exempt=NO_SOURCE,
    ),
)


@pytest.mark.parametrize(("rule", "command"), rows(RULES))
def test_request_rule(rule: Rule, command: str, tmp_path: Path) -> None:
    check_row(rule, command, tmp_path)


def test_rule_sets_are_literal_predicates_minus_true_exemptions() -> None:
    # A new command outside a set fails here, so its author must decide.
    every = set(DESCRIPTORS)
    runtime = every - {"version", "plan check"}
    assert {
        name for name, descriptor in DESCRIPTORS.items() if runtime_command(descriptor)
    } == runtime
    assert {name for name in DESCRIPTORS if source_location(name) is None} == set(
        NO_SOURCE
    )
    # A changed predicate or a false exemption removes rows, and fails here.
    assert {rule.name: set(rule.commands()) for rule in RULES} == {
        "malformed_json": every,
        "non_object_json": every,
        "unknown_field": every,
        "timeout_zero": runtime,
        "timeout_above_limit": runtime,
        "missing_source": every - set(NO_SOURCE),
    }
    for rule in RULES:
        check_exemptions(rule)


@pytest.mark.parametrize("command", sorted(DESCRIPTORS))
def test_minimal_request_is_valid(command: str, tmp_path: Path) -> None:
    request = minimal_request(command, tmp_path)
    DESCRIPTORS[command].request_type.model_validate(json.loads(json.dumps(request)))


@cache
def _manifest() -> dict[str, Any]:
    outcome = run_spa(["schema"], probe="capable")
    assert outcome.exit_status == 0, outcome.envelope
    return {entry["operation"]: entry for entry in outcome.envelope["operations"]}


@pytest.mark.parametrize("command", sorted(DESCRIPTORS))
def test_schema_flag_is_the_manifest_entry_without_a_probe(command: str) -> None:
    outcome = run_spa([*command.split(), "--schema"])
    assert outcome.exit_status == 0, outcome.envelope
    schema = OperationSchema.model_validate(outcome.envelope)
    assert schema.operation == f"spa {command}"
    for document in (
        schema.request_schema,
        schema.result_schema,
        schema.failure_schema,
        schema.invocation_schema,
    ):
        Draft202012Validator.check_schema(document)
    assert outcome.envelope == _manifest()[f"spa {command}"]
