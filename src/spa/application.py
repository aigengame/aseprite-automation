"""Application dispatch and outcome classification for descriptor-backed Operations."""

import json
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from spa.contracts import FailureEnvelope, RequestDetails, RuntimeFacts, RuntimeRequest, ValidationIssue
from spa.descriptors import OperationDescriptor
from spa.failures import RuntimeFailure


def _request_failure(descriptor: OperationDescriptor, issues: list[ValidationIssue]) -> FailureEnvelope:
    return FailureEnvelope(
        operation=f"spa {descriptor.name}", code="invalid_request", category="input",
        message="Invalid Operation Request", details=RequestDetails(errors=issues),
    )


def dispatch(
    descriptor: OperationDescriptor,
    input_json: str | None,
    argv_values: dict[str, Any],
    probe_runtime: Callable[[RuntimeRequest], RuntimeFacts],
) -> BaseModel | FailureEnvelope:
    try:
        values: dict[str, Any] = json.loads(input_json) if input_json is not None else {}
        if not isinstance(values, dict):
            raise ValueError("--input-json must be a JSON object")
        values.update({key: value for key, value in argv_values.items() if value is not None})
        request = descriptor.request_type.model_validate(values)
    except ValidationError as exc:
        return _request_failure(descriptor, [
            ValidationIssue(location=list(error["loc"]), code=error["type"], message=error["msg"])
            for error in exc.errors(include_context=False)
        ])
    except (json.JSONDecodeError, ValueError) as exc:
        return _request_failure(descriptor, [
            ValidationIssue(location=[], code="json_input", message=str(exc))
        ])
    try:
        return descriptor.execute(request, probe_runtime)
    except RuntimeFailure as exc:
        return exc.to_envelope(f"spa {descriptor.name}")
