"""Application dispatch and outcome classification for descriptor-backed Operations."""

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from spa.contracts import (
    FailureEnvelope,
    KernelExecutionDetails,
    NotFoundDetails,
    ProcessDetails,
    ProtocolDetails,
    RequestDetails,
    ResourceDetails,
    ValidationIssue,
)
from spa.descriptors import OperationDescriptor
from spa.ports import RuntimeIssue, RuntimeProbe


def _request_failure(
    descriptor: OperationDescriptor, issues: list[ValidationIssue]
) -> FailureEnvelope:
    return FailureEnvelope(
        operation=f"spa {descriptor.name}",
        code="invalid_request",
        category="input",
        message="Invalid Operation Request",
        details=RequestDetails(errors=issues),
    )


def _runtime_failure(
    descriptor: OperationDescriptor, issue: RuntimeIssue
) -> FailureEnvelope:
    evidence = issue.evidence
    match issue.kind:
        case "discovery_absent":
            code, category = "executable_not_found", "environment"
            details = NotFoundDetails(
                requested_path=evidence["requested_path"], searched=evidence["searched"]
            )
        case "resources_absent":
            code, category = "resource_incomplete", "environment"
            details = ResourceDetails(
                canonical_path=evidence["canonical_path"], searched=evidence["searched"]
            )
        case "launch_failed":
            code, category = "process_start_failed", "execution"
            details = ProcessDetails(executable=evidence["executable"])
        case "deadline":
            code, category = "process_timeout", "execution"
            details = ProcessDetails(
                executable=evidence["executable"], exit_status=evidence["exit_status"]
            )
        case "output_overflow":
            code, category = "output_limit_exceeded", "execution"
            details = ProcessDetails(
                executable=evidence["executable"], exit_status=evidence["exit_status"]
            )
        case "response_absent":
            code, category = "kernel_response_missing", "protocol"
            details = ProtocolDetails(response_path=evidence["response_path"])
        case "response_malformed":
            code, category = "kernel_response_invalid", "protocol"
            details = ProtocolDetails(response_path=evidence["response_path"])
        case "handler_rejected":
            code, category = "kernel_execution_failed", "execution"
            details = KernelExecutionDetails(
                response_path=evidence["response_path"], reason=evidence["reason"]
            )
        case "process_failed" | "exit_mismatch":
            code, category = "process_failed", "execution"
            details = ProcessDetails(
                executable=evidence["executable"], exit_status=evidence["exit_status"]
            )
        case _:
            raise ValueError(f"Unknown runtime issue kind: {issue.kind}")
    return FailureEnvelope(
        operation=f"spa {descriptor.name}",
        code=code,
        category=category,
        message=str(issue),
        details=details,
        diagnostics=issue.diagnostics,
    )


def dispatch(
    descriptor: OperationDescriptor,
    input_json: str | None,
    argv_values: dict[str, Any],
    probe_runtime: RuntimeProbe,
) -> BaseModel | FailureEnvelope:
    try:
        values: dict[str, Any] = (
            json.loads(input_json) if input_json is not None else {}
        )
        if not isinstance(values, dict):
            raise TypeError("--input-json must be a JSON object")
        values.update(
            {key: value for key, value in argv_values.items() if value is not None}
        )
        request = descriptor.request_type.model_validate(values)
    except ValidationError as exc:
        return _request_failure(
            descriptor,
            [
                ValidationIssue(
                    location=list(error["loc"]),
                    code=error["type"],
                    message=error["msg"],
                )
                for error in exc.errors(include_context=False)
            ],
        )
    except (json.JSONDecodeError, TypeError) as exc:
        return _request_failure(
            descriptor,
            [ValidationIssue(location=[], code="json_input", message=str(exc))],
        )
    try:
        return descriptor.execute(request, probe_runtime)
    except RuntimeIssue as exc:
        return _runtime_failure(descriptor, exc)
