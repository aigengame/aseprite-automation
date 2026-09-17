"""One registration authority for the installed meta Operations."""

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from spa.contracts import (
    FailureEnvelope,
    InfoResult,
    OperationSchema,
    RuntimeFacts,
    RuntimeRequest,
    SchemaResult,
    VersionRequest,
    VersionResult,
)


@dataclass(frozen=True)
class OperationDescriptor:
    name: str
    request_type: type[BaseModel]
    result_type: type[BaseModel]
    execute: Callable[[BaseModel, Callable[[RuntimeRequest], RuntimeFacts]], BaseModel]
    render_human: Callable[[BaseModel], str]
    requires_runtime: bool

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
            failure_schema=FailureEnvelope.model_json_schema(),
            invocation_schema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "command": {"const": command},
                    "input_json": {"type": "string"},
                    "argv": self.request_type.model_json_schema(),
                    "schema": {"type": "boolean"},
                    "json_output": {"type": "boolean"},
                    "human": {"type": "boolean"},
                },
                "required": ["command"],
                "additionalProperties": False,
                "x-cli-flags": {
                    "input_json": "--input-json",
                    "schema": "--schema",
                    "json_output": "--json",
                    "human": "--human",
                    **({"argv.aseprite": "--aseprite", "argv.timeout_seconds": "--timeout-seconds"}
                       if self.requires_runtime else {}),
                },
            },
        )


def version_result(_: VersionRequest, _probe: Callable[[RuntimeRequest], RuntimeFacts]) -> VersionResult:
    from importlib.metadata import version

    return VersionResult(spa_version=version("aseprite-automation"))


def info_result(request: RuntimeRequest, probe: Callable[[RuntimeRequest], RuntimeFacts]) -> InfoResult:
    from importlib.metadata import version

    facts = probe(request)
    return InfoResult(
        spa_version=version("aseprite-automation"),
        runtime=facts,
        supported_capabilities=[f"spa {descriptor.name}" for descriptor in OPERATIONS],
        capability_gaps=[],
    )


def schema_result(request: RuntimeRequest, probe: Callable[[RuntimeRequest], RuntimeFacts]) -> SchemaResult:
    info = info_result(request, probe)
    return SchemaResult(
        spa_version=info.spa_version,
        runtime=info.runtime,
        operations=[descriptor.schema() for descriptor in OPERATIONS],
        capability_gaps=info.capability_gaps,
    )


OPERATIONS = (
    OperationDescriptor("info", RuntimeRequest, InfoResult, info_result, lambda r: f"Aseprite {r.runtime.aseprite_version} (API {r.runtime.api_version}) at {r.runtime.canonical_path}", True),
    OperationDescriptor("version", VersionRequest, VersionResult, version_result, lambda r: f"SPA {r.spa_version}", False),
    OperationDescriptor("schema", RuntimeRequest, SchemaResult, schema_result, lambda r: "\n".join(item.operation for item in r.operations), True),
)
