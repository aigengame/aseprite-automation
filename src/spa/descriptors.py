"""One registration authority for the installed meta Operations."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, get_args

from pydantic import BaseModel

from spa.contracts import (
    InfoResult,
    OperationSchema,
    RuntimeFacts,
    RuntimeRequest,
    SchemaResult,
    VersionRequest,
    VersionResult,
    failure_schema,
)
from spa.ports import RuntimeProbe

COMMON_CLI_FLAGS = {
    "input_json": "--input-json",
    "schema": "--schema",
    "json_output": "--json",
    "human": "--human",
}
RUNTIME_CLI_FLAGS = {
    "aseprite": "--aseprite",
    "timeout_seconds": "--timeout-seconds",
}
ACCESS_FAILURE_CODES = ("invalid_request",)
RUNTIME_FAILURE_CODES = (
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
)


@dataclass(frozen=True)
class OperationDescriptor:
    name: str
    request_type: type[BaseModel]
    result_type: type[BaseModel]
    execute: Callable[..., BaseModel]
    render_human: Callable[[Any], str]
    requires_runtime: bool
    failure_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        command = f"spa {self.name}"
        operation_field = self.result_type.model_fields.get("operation")
        if (
            operation_field is None
            or get_args(operation_field.annotation) != (command,)
            or (
                not operation_field.is_required() and operation_field.default != command
            )
        ):
            raise ValueError(f"Result Operation identity does not match {command}")

    @property
    def cli_flags(self) -> dict[str, str]:
        return COMMON_CLI_FLAGS | (RUNTIME_CLI_FLAGS if self.requires_runtime else {})

    def schema(self) -> OperationSchema:
        command = f"spa {self.name}"
        return OperationSchema(
            operation=command,
            execution_kind="read",
            determinism="deterministic",
            side_effects=[],
            minimum_aseprite_version=None,
            requires_runtime=self.requires_runtime,
            request_schema=self.request_type.model_json_schema(),
            result_schema=self.result_type.model_json_schema(),
            failure_schema=failure_schema(self.failure_codes, command),
            invocation_schema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "command": {"const": command},
                    "input_json": {
                        "type": "string",
                        "description": "Inline JSON object or '-' to read one object from stdin.",
                    },
                    "argv": self.request_type.model_json_schema(),
                    "schema": {"type": "boolean"},
                    "json_output": {"type": "boolean"},
                    "human": {"type": "boolean"},
                },
                "required": ["command"],
                "additionalProperties": False,
                "x-cli-flags": self.cli_flags,
            },
        )


def version_result(_: VersionRequest, _probe: RuntimeProbe) -> VersionResult:
    from importlib.metadata import version

    return VersionResult(spa_version=version("aseprite-automation"))


def info_result(request: RuntimeRequest, probe: RuntimeProbe) -> InfoResult:
    from importlib.metadata import version

    observation = probe(request)
    facts = RuntimeFacts(
        selection_source=observation.selection_source,
        requested_path=observation.requested_path,
        discovered_path=observation.discovered_path,
        canonical_path=observation.canonical_path,
        resource_complete=True,
        resource_path=observation.resource_path,
        aseprite_version=observation.aseprite_version,
        api_version=observation.api_version,
    )
    return InfoResult(
        spa_version=version("aseprite-automation"),
        runtime=facts,
        supported_capabilities=[f"spa {descriptor.name}" for descriptor in OPERATIONS],
        capability_gaps=[],
    )


def schema_result(request: RuntimeRequest, probe: RuntimeProbe) -> SchemaResult:
    info = info_result(request, probe)
    return SchemaResult(
        spa_version=info.spa_version,
        runtime=info.runtime,
        operations=[descriptor.schema() for descriptor in OPERATIONS],
        access_failure_schema=failure_schema(ACCESS_FAILURE_CODES, "spa"),
        capability_gaps=info.capability_gaps,
    )


OPERATIONS = (
    OperationDescriptor(
        "info",
        RuntimeRequest,
        InfoResult,
        info_result,
        lambda r: (
            f"Aseprite {r.runtime.aseprite_version} (API {r.runtime.api_version}) at {r.runtime.canonical_path}"
        ),
        True,
        RUNTIME_FAILURE_CODES,
    ),
    OperationDescriptor(
        "version",
        VersionRequest,
        VersionResult,
        version_result,
        lambda r: f"SPA {r.spa_version}",
        False,
        ("invalid_request",),
    ),
    OperationDescriptor(
        "schema",
        RuntimeRequest,
        SchemaResult,
        schema_result,
        lambda r: "\n".join(item.operation for item in r.operations),
        True,
        RUNTIME_FAILURE_CODES,
    ),
)
