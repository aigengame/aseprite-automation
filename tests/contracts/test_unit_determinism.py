"""Execution classification is the same in registration and discovery schemas."""

from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from spa.application.failure_registry import FAILURE_CODES
from spa.application.script import SCRIPT_OPERATIONS
from spa.contracts.public import OperationSchema


@pytest.mark.parametrize("kind", ["read", "mutation", "export", "script-run"])
@pytest.mark.parametrize(
    "determinism", ["deterministic", "native-stochastic", "caller-defined"]
)
def test_schema_accepts_only_the_declared_classification_pairing(
    kind, determinism
) -> None:
    payload = SCRIPT_OPERATIONS[0].schema(FAILURE_CODES).model_dump()
    payload.update(execution_kind=kind, determinism=determinism)
    allowed = (kind == "script-run") == (determinism == "caller-defined")
    schema = OperationSchema.model_json_schema()
    assert Draft202012Validator(schema).is_valid(payload) is allowed
    if allowed:
        assert OperationSchema.model_validate(payload).determinism == determinism
    else:
        with pytest.raises(ValidationError):
            OperationSchema.model_validate(payload)


@pytest.mark.parametrize(
    "kind,determinism",
    [
        ("read", "caller-defined"),
        ("mutation", "caller-defined"),
        ("export", "caller-defined"),
        ("script-run", "deterministic"),
        ("script-run", "native-stochastic"),
    ],
)
def test_descriptor_rejects_invalid_classification(kind, determinism) -> None:
    with pytest.raises(ValueError, match="[Dd]eterminism|caller-defined"):
        replace(SCRIPT_OPERATIONS[0], execution_kind=kind, determinism=determinism)


def test_script_descriptor_cannot_register_under_an_ordinary_identity_or_in_a_plan() -> (
    None
):
    from spa.authoring.document.sprite import SPRITE_OPERATIONS

    script = SCRIPT_OPERATIONS[0]
    ordinary = SPRITE_OPERATIONS[0]
    with pytest.raises(ValueError, match="script run"):
        replace(script, name=ordinary.name, result_type=ordinary.result_type)
    with pytest.raises(ValueError, match="Plan"):
        replace(script, plan_eligible=True)
    with pytest.raises(ValueError, match="script run"):
        replace(script, execution_kind="mutation", determinism="deterministic")


def test_script_result_cannot_claim_success_for_an_unobserved_or_failed_exit() -> None:
    from spa.contracts.caller_script import ScriptRunResult

    result = {
        "executable": "/aseprite",
        "working_directory": "/tmp",
        "timeout_seconds": 15.0,
        "output_limit_bytes": 65536,
        "diagnostics": {"stdout": "", "stderr": "", "exit_status": 0},
        "files": [],
    }
    validator = Draft202012Validator(ScriptRunResult.model_json_schema())
    validator.validate(result)
    for status in (None, 1, -9):
        result["diagnostics"]["exit_status"] = status
        assert not validator.is_valid(result)
        with pytest.raises(ValidationError):
            ScriptRunResult.model_validate(result)
