"""Public Failure Code registration and schema conformance for issue #64."""

from dataclasses import replace
from functools import partial
from inspect import getsource
from types import MappingProxyType
from typing import Literal

import pytest
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaError
from pydantic import ValidationError

from spa.application import _runtime_failure, dispatch
from spa.contracts import (
    FailureEnvelope,
    KernelExecutionDetails,
    KernelProtocolDetail,
    NotFoundDetails,
    ProcessDetails,
    ProcessStartDetails,
    RequestDetails,
    ResourceDetails,
    RuntimeCompatibilityDetails,
    ValidationIssue,
    VersionRequest,
    VersionResult,
    failure_envelope,
    failure_schema,
    register_failure_codes,
)
from spa.descriptors import ACCESS_FAILURE_CODES, OPERATIONS
from spa.export import ArtifactFileDetails, ArtifactVerificationDetails
from spa.failure_registry import FAILURE_CODES
from spa.layer import LayerAddress, LayerTargetDetails
from spa.mutation import TargetCommitDetails
from spa.ports import (
    ArtifactFileEvidence,
    ArtifactVerificationEvidence,
    DiscoveryEvidence,
    HandlerEvidence,
    LaunchEvidence,
    PostconditionEvidence,
    ProcessEvidence,
    ResourceEvidence,
    ResponseEvidence,
    RuntimeCompatibilityEvidence,
    RuntimeIssue,
    TargetCommitEvidence,
)
from spa.sprite import SpriteCopyStagingDetails, SpriteUnsupportedContentDetails
from tests.support import operation_services

registered_failure_envelope = partial(failure_envelope, failure_codes=FAILURE_CODES)
registered_failure_schema = partial(failure_schema, failure_codes=FAILURE_CODES)

RUNTIME_ISSUE_CASES = (
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
    ("postcondition_failed", "kernel_response_invalid"),
    ("runtime_incompatible", "runtime_incompatible"),
)


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
        "runtime_incompatible",
        "target_commit_failed",
        "artifact_file_failed",
        "artifact_verification_failed",
        "sprite_copy_staging_failed",
        "sprite_flatten_unsupported_content",
    } <= set(FAILURE_CODES)
    assert all(
        spec.meaning and spec.code == code for code, spec in FAILURE_CODES.items()
    )


def test_installed_failure_registry_is_one_immutable_composition() -> None:
    from spa import contracts

    assert isinstance(FAILURE_CODES, MappingProxyType)
    assert "FAILURE_CODES" not in vars(contracts)
    assert "install_failure_codes" not in vars(contracts)
    assert "failure_registry" not in getsource(contracts)
    assert TargetCommitDetails.__module__ == "spa.mutation"


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
    outcome = registered_failure_envelope(
        "spa version",
        "invalid_request",
        "bad",
        details,
        applicable_codes=("invalid_request",),
    )
    assert outcome.category == "input"
    with pytest.raises(ValueError, match="Unknown Failure Code"):
        registered_failure_envelope(
            "spa version",
            "not_registered",
            "bad",
            details,
            applicable_codes=("invalid_request",),
        )
    with pytest.raises(ValueError, match="Details"):
        registered_failure_envelope(
            "spa version",
            "invalid_request",
            "bad",
            ProcessDetails(executable="x"),
            applicable_codes=("invalid_request",),
        )
    with pytest.raises(ValueError, match="not applicable"):
        registered_failure_envelope(
            "spa version",
            "process_start_failed",
            "bad",
            ProcessStartDetails(executable="x", exit_status=None),
            applicable_codes=("invalid_request",),
        )


def test_each_registered_code_has_a_constrained_public_schema() -> None:
    details_by_type = {
        RequestDetails: RequestDetails(errors=[]),
        NotFoundDetails: NotFoundDetails(requested_path=None, searched=[]),
        ResourceDetails: ResourceDetails(canonical_path="/aseprite", searched=[]),
        ProcessStartDetails: ProcessStartDetails(
            executable="/aseprite", exit_status=None
        ),
        ProcessDetails: ProcessDetails(executable="/aseprite"),
        KernelProtocolDetail: KernelProtocolDetail(response_path="/response.json"),
        KernelExecutionDetails: KernelExecutionDetails(
            response_path="/response.json", reason="refused"
        ),
        RuntimeCompatibilityDetails: RuntimeCompatibilityDetails(
            aseprite_version="old",
            lua_version="Lua 5.3",
            api_version=40,
            required_lua_language="Lua 5.4",
            minimum_api_version=41,
            missing_capabilities=["aseprite_runtime_introspection"],
        ),
        TargetCommitDetails: TargetCommitDetails(
            target_sprite_file="sprite.aseprite", reason="target_not_file"
        ),
        SpriteCopyStagingDetails: SpriteCopyStagingDetails(
            source_sprite_file="source.aseprite", target_sprite_file="copy.aseprite"
        ),
        ArtifactFileDetails: ArtifactFileDetails(
            path="image.png", reason="destination_exists"
        ),
        ArtifactVerificationDetails: ArtifactVerificationDetails(
            path="image.png", reason="content mismatch"
        ),
        LayerTargetDetails: LayerTargetDetails(
            address_role="target", address=LayerAddress(layer_path=[1])
        ),
        SpriteUnsupportedContentDetails: SpriteUnsupportedContentDetails(
            source_sprite_file="sprite.aseprite",
            tileset_count=1,
            tilemap_layer_count=0,
        ),
    }
    for code, spec in FAILURE_CODES.items():
        schema = registered_failure_schema((code,), "spa info")
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        details_schema = spec.details_type.model_json_schema()
        assert details_schema["properties"]["kind"]["const"] == spec.details_kind
        outcome = registered_failure_envelope(
            "spa info",
            code,
            "failed",
            details_by_type[spec.details_type],
            applicable_codes=(code,),
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


def test_kernel_protocol_detail_does_not_expose_private_version() -> None:
    outcome = registered_failure_envelope(
        "spa info",
        "kernel_response_invalid",
        "invalid response",
        KernelProtocolDetail(response_path="/response.json"),
        applicable_codes=("kernel_response_invalid",),
    ).model_dump(mode="json")
    details = outcome["details"]
    assert outcome["category"] == "kernel_protocol"
    assert details["kind"] == "kernel_protocol"
    assert set(details) == {
        "kind",
        "response_path",
        "failed_step",
        "failed_operation",
    }
    assert details["failed_step"] is None
    assert details["failed_operation"] is None
    validator = Draft202012Validator(
        registered_failure_schema(("kernel_response_invalid",), "spa info")
    )
    validator.validate(outcome)
    assert not validator.is_valid(outcome | {"category": "protocol"})
    for field in ("protocol_version", "kernel_protocol_version"):
        assert not validator.is_valid(outcome | {"details": details | {field: 1}})


def test_process_start_failure_cannot_claim_a_process_exit_status() -> None:
    with pytest.raises(ValidationError):
        ProcessStartDetails(executable="/aseprite", exit_status=7)
    failure = registered_failure_envelope(
        "spa info",
        "process_start_failed",
        "launch denied",
        ProcessStartDetails(executable="/aseprite", exit_status=None),
        applicable_codes=("process_start_failed",),
    ).model_dump(mode="json")
    validator = Draft202012Validator(
        registered_failure_schema(("process_start_failed",), "spa info")
    )
    validator.validate(failure)
    assert not validator.is_valid(
        failure | {"details": failure["details"] | {"exit_status": 7}}
    )
    with pytest.raises(ValueError, match="Details"):
        registered_failure_envelope(
            "spa info",
            "process_start_failed",
            "launch denied",
            ProcessDetails(executable="/aseprite", exit_status=7),
            applicable_codes=("process_start_failed",),
        )


def test_failure_schema_refuses_unknown_and_duplicate_applicability() -> None:
    with pytest.raises(ValueError, match="Unknown Failure Code"):
        registered_failure_schema(("not_registered",), "spa")
    with pytest.raises(ValueError, match="unique"):
        registered_failure_schema(("invalid_request", "invalid_request"), "spa")


def test_failure_schema_rejects_wrong_code_category_details_and_missing_fields() -> (
    None
):
    outcome = registered_failure_envelope(
        "spa version",
        "invalid_request",
        "bad",
        RequestDetails(
            errors=[ValidationIssue(location=[], code="test", message="bad")]
        ),
        applicable_codes=("invalid_request",),
    ).model_dump(mode="json")
    validator = Draft202012Validator(
        registered_failure_schema(("invalid_request",), "spa version")
    )
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
    with pytest.raises(SchemaError):
        validator.validate(outcome | {"operation": "spa info"})


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
        "runtime_incompatible",
    }
    assert by_name["schema"].failure_codes == by_name["info"].failure_codes
    failure = registered_failure_envelope(
        "spa info",
        "process_start_failed",
        "launch denied",
        ProcessStartDetails(executable="x", exit_status=None),
        applicable_codes=by_name["info"].failure_codes,
    ).model_dump(mode="json")
    Draft202012Validator(by_name["info"].schema(FAILURE_CODES).failure_schema).validate(
        failure
    )
    with pytest.raises(SchemaError):
        Draft202012Validator(
            by_name["version"].schema(FAILURE_CODES).failure_schema
        ).validate(failure)


def test_registry_and_access_applicability_are_closed_over_installed_producers() -> (
    None
):
    # run_cli currently produces only invalid_request before Descriptor selection.
    # A later Access code needs its own CLI producer witness in the same feature slice.
    assert ACCESS_FAILURE_CODES == ("invalid_request",)
    declared = set(ACCESS_FAILURE_CODES)
    for descriptor in OPERATIONS:
        declared.update(descriptor.failure_codes)
    assert set(FAILURE_CODES) == declared
    info = next(descriptor for descriptor in OPERATIONS if descriptor.name == "info")
    assert set(info.failure_codes) == {"invalid_request"} | {
        code for _, code in RUNTIME_ISSUE_CASES
    }
    access_schema = Draft202012Validator(
        registered_failure_schema(ACCESS_FAILURE_CODES, "spa")
    )
    access_failure = registered_failure_envelope(
        "spa",
        "invalid_request",
        "bad",
        RequestDetails(errors=[]),
        applicable_codes=ACCESS_FAILURE_CODES,
    ).model_dump(mode="json")
    access_schema.validate(access_failure)
    assert not access_schema.is_valid(access_failure | {"operation": "spa version"})
    other_failure = registered_failure_envelope(
        "spa",
        "process_start_failed",
        "failed",
        ProcessStartDetails(executable="x", exit_status=None),
        applicable_codes=info.failure_codes,
    ).model_dump(mode="json")
    assert not access_schema.is_valid(other_failure)


def test_descriptor_rejects_result_operation_identity_mismatch() -> None:
    version = next(
        descriptor for descriptor in OPERATIONS if descriptor.name == "version"
    )
    with pytest.raises(ValueError, match="Result Operation identity"):
        replace(version, name="renamed")


def test_descriptor_rejects_result_operation_with_stale_default() -> None:
    class RenamedResult(VersionResult):
        operation: Literal["spa renamed"] = "spa version"

    version = next(
        descriptor for descriptor in OPERATIONS if descriptor.name == "version"
    )
    with pytest.raises(ValueError, match="Result Operation identity"):
        replace(version, name="renamed", result_type=RenamedResult)


def test_runtime_descriptor_declares_compatibility_failure() -> None:
    info = next(descriptor for descriptor in OPERATIONS if descriptor.name == "info")

    with pytest.raises(ValueError, match="runtime_incompatible"):
        replace(info, failure_codes=("invalid_request",))


def test_application_refuses_failure_not_declared_by_selected_descriptor() -> None:
    version = next(
        descriptor for descriptor in OPERATIONS if descriptor.name == "version"
    )

    def launch_issue(_request: object, _probe: object) -> None:
        raise RuntimeIssue(
            "launch_failed", "failed", LaunchEvidence(executable="/aseprite")
        )

    misclassified = replace(version, execute=launch_issue)
    with pytest.raises(ValueError, match="not applicable to spa version"):
        dispatch(
            misclassified,
            None,
            {},
            operation_services(lambda _request: None),
            FAILURE_CODES,
        )


def test_application_refuses_result_outside_descriptor_contract() -> None:
    version = next(
        descriptor for descriptor in OPERATIONS if descriptor.name == "version"
    )
    wrong_result = replace(version, execute=lambda _request, _probe: VersionRequest())
    with pytest.raises(TypeError, match="Operation Result does not match spa version"):
        dispatch(
            wrong_result,
            None,
            {},
            operation_services(lambda _request: None),
            FAILURE_CODES,
        )

    wrong_failure = FailureEnvelope(
        operation="spa version",
        code="process_failed",
        category="execution",
        message="failed",
        details=ProcessDetails(executable="/aseprite", exit_status=7),
    )
    wrong_failure_result = replace(
        version, execute=lambda _request, _probe: wrong_failure
    )
    with pytest.raises(ValueError, match="not applicable to spa version"):
        dispatch(
            wrong_failure_result,
            None,
            {},
            operation_services(lambda _request: None),
            FAILURE_CODES,
        )


def test_runtime_issue_requires_kind_specific_private_evidence() -> None:
    with pytest.raises(TypeError, match="Invalid private evidence"):
        RuntimeIssue("launch_failed", "failed", {})


def _evidence_for(kind: str):
    if kind == "discovery_absent":
        return DiscoveryEvidence(requested_path=None, searched=[])
    if kind == "resources_absent":
        return ResourceEvidence(canonical_path="/aseprite", searched=[])
    if kind == "launch_failed":
        return LaunchEvidence(executable="/aseprite")
    if kind in {"deadline", "output_overflow", "process_failed", "exit_mismatch"}:
        return ProcessEvidence(executable="/aseprite", exit_status=13)
    if kind in {"response_absent", "response_malformed"}:
        return ResponseEvidence(response_path="/response.json")
    if kind == "handler_rejected":
        return HandlerEvidence(response_path="/response.json", reason="refused")
    if kind == "postcondition_failed":
        return PostconditionEvidence(
            response_path="/response.json", reason="incomplete"
        )
    if kind == "runtime_incompatible":
        return RuntimeCompatibilityEvidence(
            aseprite_version="old",
            lua_version="Lua 5.3",
            api_version=40,
            required_lua_language="Lua 5.4",
            minimum_api_version=41,
            missing_capabilities=("aseprite_runtime_introspection",),
        )
    raise AssertionError(kind)


@pytest.mark.parametrize(("kind", "expected_code"), RUNTIME_ISSUE_CASES)
def test_every_runtime_issue_kind_classifies_to_a_registered_failure(
    kind: str, expected_code: str
) -> None:
    info = next(descriptor for descriptor in OPERATIONS if descriptor.name == "info")
    outcome = _runtime_failure(
        info,
        RuntimeIssue(kind, "failed", _evidence_for(kind)),
        FAILURE_CODES,
    )
    assert outcome.code == expected_code
    assert outcome.category == FAILURE_CODES[expected_code].category
    Draft202012Validator(info.schema(FAILURE_CODES).failure_schema).validate(
        outcome.model_dump(mode="json")
    )


def test_target_commit_failure_is_owned_by_mutating_sprite_operation() -> None:
    create = next(
        descriptor for descriptor in OPERATIONS if descriptor.name == "sprite create"
    )
    outcome = _runtime_failure(
        create,
        RuntimeIssue(
            "target_commit_failed",
            "failed",
            TargetCommitEvidence(
                target_sprite_file="sprite.aseprite", reason="target_not_file"
            ),
        ),
        FAILURE_CODES,
    )
    assert outcome.code == "target_commit_failed"
    assert outcome.details == TargetCommitDetails(
        target_sprite_file="sprite.aseprite", reason="target_not_file"
    )
    Draft202012Validator(create.schema(FAILURE_CODES).failure_schema).validate(
        outcome.model_dump(mode="json")
    )


@pytest.mark.parametrize(
    ("kind", "evidence", "details_type"),
    [
        (
            "artifact_file_failed",
            ArtifactFileEvidence("image.png", "destination_exists"),
            ArtifactFileDetails,
        ),
        (
            "artifact_verification_failed",
            ArtifactVerificationEvidence("image.png", "content mismatch"),
            ArtifactVerificationDetails,
        ),
    ],
)
def test_export_failures_are_owned_by_export_image(
    kind: str,
    evidence: ArtifactFileEvidence | ArtifactVerificationEvidence,
    details_type: type[ArtifactFileDetails] | type[ArtifactVerificationDetails],
) -> None:
    export = next(
        descriptor for descriptor in OPERATIONS if descriptor.name == "export image"
    )
    outcome = _runtime_failure(
        export, RuntimeIssue(kind, "failed", evidence), FAILURE_CODES
    )
    assert outcome.code == kind
    assert isinstance(outcome.details, details_type)
    Draft202012Validator(export.schema(FAILURE_CODES).failure_schema).validate(
        outcome.model_dump(mode="json")
    )
