"""Application dispatch and outcome classification for descriptor-backed Operations."""

import json
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from pydantic import BaseModel, ValidationError

from spa.contracts import (
    FailureCodeSpec,
    FailureEnvelope,
    KernelExecutionDetails,
    KernelProtocolDetail,
    NotFoundDetails,
    ProcessDetails,
    ProcessStartDetails,
    RequestDetails,
    ResourceDetails,
    RuntimeCapability,
    RuntimeCompatibilityDetails,
    RuntimeRequest,
    ValidationIssue,
    failure_envelope,
)
from spa.export import ArtifactFileDetails, ArtifactVerificationDetails
from spa.mutation import TargetCommitDetails
from spa.operation import OperationDescriptor
from spa.ports import (
    ArtifactFileEvidence,
    ArtifactVerificationEvidence,
    DiscoveryEvidence,
    HandlerEvidence,
    LaunchEvidence,
    OperationServices,
    PostconditionEvidence,
    ProcessEvidence,
    ResourceEvidence,
    ResponseEvidence,
    RuntimeCompatibilityEvidence,
    RuntimeIssue,
    RuntimeObservation,
    TargetCommitEvidence,
)


def _request_failure(
    descriptor: OperationDescriptor[Any, Any],
    issues: list[ValidationIssue],
    failure_codes: Mapping[str, FailureCodeSpec],
) -> FailureEnvelope:
    return failure_envelope(
        operation=f"spa {descriptor.name}",
        code="invalid_request",
        message="Invalid Operation Request",
        details=RequestDetails(errors=issues),
        applicable_codes=descriptor.failure_codes,
        failure_codes=failure_codes,
    )


def _runtime_failure(
    descriptor: OperationDescriptor[Any, Any],
    issue: RuntimeIssue,
    failure_codes: Mapping[str, FailureCodeSpec],
) -> FailureEnvelope:
    match issue.kind, issue.evidence:
        case "discovery_absent", DiscoveryEvidence() as evidence:
            code = "executable_not_found"
            details = NotFoundDetails(
                requested_path=evidence.requested_path, searched=evidence.searched
            )
        case "resources_absent", ResourceEvidence() as evidence:
            code = "resource_incomplete"
            details = ResourceDetails(
                canonical_path=evidence.canonical_path, searched=evidence.searched
            )
        case "launch_failed", LaunchEvidence() as evidence:
            code = "process_start_failed"
            details = ProcessStartDetails(
                executable=evidence.executable, exit_status=None
            )
        case "deadline", ProcessEvidence() as evidence:
            code = "process_timeout"
            details = ProcessDetails(
                executable=evidence.executable, exit_status=evidence.exit_status
            )
        case "output_overflow", ProcessEvidence() as evidence:
            code = "output_limit_exceeded"
            details = ProcessDetails(
                executable=evidence.executable, exit_status=evidence.exit_status
            )
        case "response_absent", ResponseEvidence() as evidence:
            code = "kernel_response_missing"
            details = KernelProtocolDetail(response_path=evidence.response_path)
        case "response_malformed", ResponseEvidence() as evidence:
            code = "kernel_response_invalid"
            details = KernelProtocolDetail(response_path=evidence.response_path)
        case "handler_rejected", HandlerEvidence() as evidence:
            code = "kernel_execution_failed"
            details = KernelExecutionDetails(
                response_path=evidence.response_path, reason=evidence.reason
            )
        case "postcondition_failed", PostconditionEvidence() as evidence:
            code = "kernel_response_invalid"
            details = KernelProtocolDetail(response_path=evidence.response_path)
        case (("process_failed" | "exit_mismatch"), ProcessEvidence() as evidence):
            code = "process_failed"
            details = ProcessDetails(
                executable=evidence.executable, exit_status=evidence.exit_status
            )
        case "runtime_incompatible", RuntimeCompatibilityEvidence() as evidence:
            code = "runtime_incompatible"
            details = RuntimeCompatibilityDetails(
                aseprite_version=evidence.aseprite_version,
                lua_version=evidence.lua_version,
                api_version=evidence.api_version,
                required_lua_language=evidence.required_lua_language,
                minimum_api_version=evidence.minimum_api_version,
                missing_capabilities=list(evidence.missing_capabilities),
            )
        case "target_commit_failed", TargetCommitEvidence() as evidence:
            code = "target_commit_failed"
            details = TargetCommitDetails(
                target_sprite_file=evidence.target_sprite_file,
                reason=evidence.reason,
            )
        case "artifact_file_failed", ArtifactFileEvidence() as evidence:
            code = "artifact_file_failed"
            details = ArtifactFileDetails(path=evidence.path, reason=evidence.reason)
        case "artifact_verification_failed", ArtifactVerificationEvidence() as evidence:
            code = "artifact_verification_failed"
            details = ArtifactVerificationDetails(
                path=evidence.path, reason=evidence.reason
            )
        case _:
            raise ValueError(f"Unknown runtime issue kind: {issue.kind}")
    return failure_envelope(
        operation=f"spa {descriptor.name}",
        code=code,
        message=str(issue),
        details=details,
        applicable_codes=descriptor.failure_codes,
        failure_codes=failure_codes,
        diagnostics=issue.diagnostics,
    )


def _validated_outcome(
    descriptor: OperationDescriptor[Any, Any],
    outcome: BaseModel | FailureEnvelope,
    failure_codes: Mapping[str, FailureCodeSpec],
) -> BaseModel | FailureEnvelope:
    operation = f"spa {descriptor.name}"
    if isinstance(outcome, FailureEnvelope):
        if outcome.operation != operation:
            raise ValueError(f"Failure Operation does not match {operation}")
        return failure_envelope(
            operation=operation,
            code=outcome.code,
            message=outcome.message,
            details=outcome.details,
            applicable_codes=descriptor.failure_codes,
            failure_codes=failure_codes,
            diagnostics=outcome.diagnostics,
        )
    if not isinstance(outcome, descriptor.result_type):
        raise TypeError(f"Operation Result does not match {operation}")
    return descriptor.result_type.model_validate(outcome.model_dump())


def dispatch(
    descriptor: OperationDescriptor[Any, Any],
    input_json: str | None,
    argv_values: dict[str, Any],
    dependencies: OperationServices,
    failure_codes: Mapping[str, FailureCodeSpec],
) -> BaseModel | FailureEnvelope:
    configured = dependencies
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
            failure_codes,
        )
    except (json.JSONDecodeError, TypeError) as exc:
        return _request_failure(
            descriptor,
            [ValidationIssue(location=[], code="json_input", message=str(exc))],
            failure_codes,
        )

    observation: RuntimeObservation | None = None

    def compatible_probe(runtime_request: RuntimeRequest) -> RuntimeObservation:
        nonlocal observation
        if observation is None:
            observation = configured.probe_runtime(runtime_request)
            requirements = descriptor.runtime_requirements
            if requirements is None:
                return observation
            missing: tuple[RuntimeCapability, ...] = tuple(
                capability
                for capability in requirements.required_capabilities
                if capability not in observation.verified_capabilities
            )
            if (
                observation.lua_version != requirements.lua_language
                or observation.api_version < requirements.minimum_api_version
                or missing
            ):
                raise RuntimeIssue(
                    "runtime_incompatible",
                    "Installed Aseprite runtime does not meet the Operation requirements",
                    RuntimeCompatibilityEvidence(
                        aseprite_version=observation.aseprite_version,
                        lua_version=observation.lua_version,
                        api_version=observation.api_version,
                        required_lua_language=requirements.lua_language,
                        minimum_api_version=requirements.minimum_api_version,
                        missing_capabilities=missing,
                    ),
                )
        return observation

    try:
        if descriptor.runtime_requirements is not None:
            if not isinstance(request, RuntimeRequest):
                raise TypeError("Runtime Operation Request must extend RuntimeRequest")
            compatible_probe(request)
        outcome = descriptor.execute(
            request, replace(configured, probe_runtime=compatible_probe)
        )
    except RuntimeIssue as exc:
        return _runtime_failure(descriptor, exc, failure_codes)
    return _validated_outcome(descriptor, outcome, failure_codes)
