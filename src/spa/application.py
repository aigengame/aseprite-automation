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
    ProcessStartDetails,
    RequestDetails,
    ResourceDetails,
    ValidationIssue,
    failure_envelope,
)
from spa.descriptors import OperationDescriptor
from spa.ports import (
    DiscoveryEvidence,
    HandlerEvidence,
    LaunchEvidence,
    ProcessEvidence,
    ResourceEvidence,
    ResponseEvidence,
    RuntimeIssue,
    RuntimeProbe,
)


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
            assert isinstance(evidence, DiscoveryEvidence)
            code = "executable_not_found"
            details = NotFoundDetails(
                requested_path=evidence.requested_path, searched=evidence.searched
            )
        case "resources_absent":
            assert isinstance(evidence, ResourceEvidence)
            code = "resource_incomplete"
            details = ResourceDetails(
                canonical_path=evidence.canonical_path, searched=evidence.searched
            )
        case "launch_failed":
            assert isinstance(evidence, LaunchEvidence)
            code = "process_start_failed"
            details = ProcessStartDetails(
                executable=evidence.executable, exit_status=None
            )
        case "deadline":
            assert isinstance(evidence, ProcessEvidence)
            code = "process_timeout"
            details = ProcessDetails(
                executable=evidence.executable, exit_status=evidence.exit_status
            )
        case "output_overflow":
            assert isinstance(evidence, ProcessEvidence)
            code = "output_limit_exceeded"
            details = ProcessDetails(
                executable=evidence.executable, exit_status=evidence.exit_status
            )
        case "response_absent":
            assert isinstance(evidence, ResponseEvidence)
            code = "kernel_response_missing"
            details = KernelProtocolDetail(response_path=evidence.response_path)
        case "response_malformed":
            assert isinstance(evidence, ResponseEvidence)
            code = "kernel_response_invalid"
            details = KernelProtocolDetail(response_path=evidence.response_path)
        case "handler_rejected":
            assert isinstance(evidence, HandlerEvidence)
            code = "kernel_execution_failed"
            details = KernelExecutionDetails(
                response_path=evidence.response_path, reason=evidence.reason
            )
        case "process_failed" | "exit_mismatch":
            assert isinstance(evidence, ProcessEvidence)
            code = "process_failed"
            details = ProcessDetails(
                executable=evidence.executable, exit_status=evidence.exit_status
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


def _validated_outcome(
    descriptor: OperationDescriptor, outcome: BaseModel | FailureEnvelope
) -> BaseModel | FailureEnvelope:
    operation = f"spa {descriptor.name}"
    if isinstance(outcome, FailureEnvelope):
        validated = FailureEnvelope.model_validate(outcome.model_dump())
        if validated.operation != operation:
            raise ValueError(f"Failure Operation does not match {operation}")
        return failure_envelope(
            operation=operation,
            code=validated.code,
            message=validated.message,
            details=validated.details,
            applicable_codes=descriptor.failure_codes,
            diagnostics=validated.diagnostics,
        )
    if not isinstance(outcome, descriptor.result_type):
        raise TypeError(f"Operation Result does not match {operation}")
    return descriptor.result_type.model_validate(outcome.model_dump())


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
        outcome = descriptor.execute(request, probe_runtime)
    except RuntimeIssue as exc:
        return _runtime_failure(descriptor, exc)
    return _validated_outcome(descriptor, outcome)
