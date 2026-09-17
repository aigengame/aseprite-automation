"""Public Failure Code registration and schema conformance for issue #64."""

from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaError
from pydantic import ValidationError

from spa.application import _runtime_failure
from spa.contracts import (
    FAILURE_CODES,
    FailureEnvelope,
    KernelExecutionDetails,
    NotFoundDetails,
    ProcessDetails,
    ProtocolDetails,
    RequestDetails,
    ResourceDetails,
    ValidationIssue,
    failure_envelope,
    failure_schema,
    register_failure_codes,
)
from spa.descriptors import OPERATIONS
from spa.ports import RuntimeIssue


def test_all_installed_failure_codes_are_registered_once() -> None:
    assert {
        "invalid_request",
        "executable_not_found",
        "resource_incomplete",
        "process_start_failed",
        "process_timeout",
        "output_limit_exceeded",
        "process_failed",
        "kernel_response_missing",
        "kernel_response_invalid",
        "kernel_execution_failed",
    } <= set(FAILURE_CODES)
    assert all(
        spec.meaning and spec.code == code for code, spec in FAILURE_CODES.items()
    )


def test_registration_refuses_duplicate_invalid_and_unsupported_entries() -> None:
    spec = FAILURE_CODES["invalid_request"]
    with pytest.raises(ValueError, match="Duplicate"):
        register_failure_codes((spec, spec))
    with pytest.raises(ValueError, match="lower_snake_case"):
        register_failure_codes((replace(spec, code="INVALID_REQUEST"),))
    with pytest.raises(ValueError, match="Details"):
        register_failure_codes((replace(spec, details_type=FailureEnvelope),))


def test_failure_construction_derives_category_and_refuses_mismatch() -> None:
    details = RequestDetails(
        errors=[ValidationIssue(location=[], code="test", message="bad")]
    )
    outcome = failure_envelope("spa version", "invalid_request", "bad", details)
    assert outcome.category == "input"
    with pytest.raises(ValueError, match="Unknown Failure Code"):
        failure_envelope("spa version", "not_registered", "bad", details)
    with pytest.raises(ValueError, match="Details"):
        failure_envelope(
            "spa version", "invalid_request", "bad", ProcessDetails(executable="x")
        )
    with pytest.raises(ValidationError, match="Category"):
        FailureEnvelope(
            operation="spa version",
            code="invalid_request",
            category="execution",
            message="bad",
            details=details,
        )
    with pytest.raises(ValidationError, match="Unknown Failure Code"):
        FailureEnvelope(
            operation="spa version",
            code="not_registered",
            category="input",
            message="bad",
            details=details,
        )


def test_each_registered_code_has_a_constrained_public_schema() -> None:
    details_by_type = {
        RequestDetails: RequestDetails(errors=[]),
        NotFoundDetails: NotFoundDetails(requested_path=None, searched=[]),
        ResourceDetails: ResourceDetails(canonical_path="/aseprite", searched=[]),
        ProcessDetails: ProcessDetails(executable="/aseprite"),
        ProtocolDetails: ProtocolDetails(response_path="/response.json"),
        KernelExecutionDetails: KernelExecutionDetails(
            response_path="/response.json", reason="refused"
        ),
    }
    for code, spec in FAILURE_CODES.items():
        schema = failure_schema((code,))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        details_schema = spec.details_type.model_json_schema()
        assert details_schema["properties"]["kind"]["const"] == spec.details_kind
        outcome = failure_envelope(
            "spa info", code, "failed", details_by_type[spec.details_type]
        ).model_dump(mode="json")
        validator.validate(outcome)
        assert not validator.is_valid(
            outcome | {"category": "input" if spec.category != "input" else "execution"}
        )
        wrong_details = (
            ProcessDetails(executable="/aseprite")
            if spec.details_type is RequestDetails
            else RequestDetails(errors=[])
        )
        assert not validator.is_valid(
            outcome | {"details": wrong_details.model_dump(mode="json")}
        )


def test_failure_schema_refuses_unknown_and_duplicate_applicability() -> None:
    with pytest.raises(ValueError, match="Unknown Failure Code"):
        failure_schema(("not_registered",))
    with pytest.raises(ValueError, match="unique"):
        failure_schema(("invalid_request", "invalid_request"))


def test_failure_schema_rejects_wrong_code_category_details_and_missing_fields() -> (
    None
):
    outcome = failure_envelope(
        "spa version",
        "invalid_request",
        "bad",
        RequestDetails(
            errors=[ValidationIssue(location=[], code="test", message="bad")]
        ),
    ).model_dump(mode="json")
    validator = Draft202012Validator(failure_schema(("invalid_request",)))
    validator.validate(outcome)
    for field, value in (
        ("code", "process_failed"),
        ("category", "execution"),
        ("details", {"kind": "process", "executable": "x"}),
    ):
        with pytest.raises(SchemaError):
            validator.validate(outcome | {field: value})
    for field in ("status", "code", "category"):
        changed = outcome.copy()
        del changed[field]
        with pytest.raises(SchemaError):
            validator.validate(changed)
    changed = outcome.copy()
    changed["details"] = {"errors": outcome["details"]["errors"]}
    with pytest.raises(SchemaError):
        validator.validate(changed)


def test_descriptor_applicability_does_not_advertise_other_codes() -> None:
    by_name = {descriptor.name: descriptor for descriptor in OPERATIONS}
    assert by_name["version"].failure_codes == ("invalid_request",)
    assert set(by_name["info"].failure_codes) == {
        "invalid_request",
        "executable_not_found",
        "resource_incomplete",
        "process_start_failed",
        "process_timeout",
        "output_limit_exceeded",
        "process_failed",
        "kernel_response_missing",
        "kernel_response_invalid",
        "kernel_execution_failed",
    }
    assert by_name["schema"].failure_codes == by_name["info"].failure_codes
    failure = failure_envelope(
        "spa info",
        "process_start_failed",
        "launch denied",
        ProcessDetails(executable="x"),
    ).model_dump(mode="json")
    Draft202012Validator(by_name["info"].schema().failure_schema).validate(failure)
    with pytest.raises(SchemaError):
        Draft202012Validator(by_name["version"].schema().failure_schema).validate(
            failure
        )


@pytest.mark.parametrize(
    ("kind", "expected_code"),
    [
        ("discovery_absent", "executable_not_found"),
        ("resources_absent", "resource_incomplete"),
        ("launch_failed", "process_start_failed"),
        ("deadline", "process_timeout"),
        ("output_overflow", "output_limit_exceeded"),
        ("process_failed", "process_failed"),
        ("exit_mismatch", "process_failed"),
        ("response_absent", "kernel_response_missing"),
        ("response_malformed", "kernel_response_invalid"),
        ("handler_rejected", "kernel_execution_failed"),
    ],
)
def test_every_runtime_issue_kind_classifies_to_a_registered_failure(
    kind: str, expected_code: str
) -> None:
    info = next(descriptor for descriptor in OPERATIONS if descriptor.name == "info")
    evidence = {
        "requested_path": None,
        "searched": [],
        "canonical_path": "/aseprite",
        "executable": "/aseprite",
        "exit_status": 13,
        "response_path": "/response.json",
        "reason": "refused",
    }
    outcome = _runtime_failure(info, RuntimeIssue(kind, "failed", evidence))
    assert outcome.code == expected_code
    assert outcome.category == FAILURE_CODES[expected_code].category
    Draft202012Validator(info.schema().failure_schema).validate(
        outcome.model_dump(mode="json")
    )
