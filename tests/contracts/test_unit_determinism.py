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
