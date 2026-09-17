"""Application dispatch and outcome classification for descriptor-backed Operations."""

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from spa.contracts import (
    FailureEnvelope,
    KernelExecutionDetails,
    KernelProtocolDetail,
    NotFoundDetails,
    ProcessDetails,
    RequestDetails,
    ResourceDetails,
    ValidationIssue,
    failure_envelope,
)
from spa.descriptors import OperationDescriptor
from spa.ports import RuntimeIssue, RuntimeProbe


def _request_failure(
    descriptor: OperationDescriptor, issues: list[ValidationIssue]
) -> FailureEnvelope:
    return failure_envelope(
        operation=f"spa {descriptor.name}",
        code="invalid_request",
        message="Invalid Operation Request",
        details=RequestDetails(errors=issues),
        applicable_codes=descriptor.failure_codes,
    )


def _runtime_failure(
    descriptor: OperationDescriptor, issue: RuntimeIssue
) -> FailureEnvelope:
    evidence = issue.evidence
    match issue.kind:
        case "discovery_absent":
            code = "executable_not_found"
            details = NotFoundDetails(
                requested_path=evidence["requested_path"], searched=evidence["searched"]
            )
        case "resources_absent":
            code = "resource_incomplete"
            details = ResourceDetails(
                canonical_path=evidence["canonical_path"], searched=evidence["searched"]
            )
        case "launch_failed":
            code = "process_start_failed"
            details = ProcessDetails(executable=evidence["executable"])
        case "deadline":
            code = "process_timeout"
            details = ProcessDetails(
                executable=evidence["executable"], exit_status=evidence["exit_status"]
            )
        case "output_overflow":
            code = "output_limit_exceeded"
            details = ProcessDetails(
                executable=evidence["executable"], exit_status=evidence["exit_status"]
            )
        case "response_absent":
            code = "kernel_response_missing"
            details = KernelProtocolDetail(response_path=evidence["response_path"])
        case "response_malformed":
            code = "kernel_response_invalid"
            details = KernelProtocolDetail(response_path=evidence["response_path"])
        case "handler_rejected":
            code = "kernel_execution_failed"
            details = KernelExecutionDetails(
                response_path=evidence["response_path"], reason=evidence["reason"]
            )
        case "process_failed" | "exit_mismatch":
            code = "process_failed"
            details = ProcessDetails(
                executable=evidence["executable"], exit_status=evidence["exit_status"]
            )
        case _:
            raise ValueError(f"Unknown runtime issue kind: {issue.kind}")
    return failure_envelope(
        operation=f"spa {descriptor.name}",
        code=code,
        message=str(issue),
        details=details,
        applicable_codes=descriptor.failure_codes,
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
