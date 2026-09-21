"""Shared Operation Descriptor mechanics at the application-contract boundary."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel

from spa.contracts import (
    OperationSchema,
    RuntimeRequest,
    RuntimeRequirements,
    failure_schema,
)
from spa.ports import OperationServices

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
    "runtime_incompatible",
)


@dataclass(frozen=True)
class OperationDescriptor[RequestT: BaseModel, ResultT: BaseModel]:
    name: str
    request_type: type[RequestT]
    result_type: type[ResultT]
    execute: Callable[[RequestT, OperationServices], ResultT]
    render_human: Callable[[ResultT], str]
    runtime_requirements: RuntimeRequirements | None
    failure_codes: tuple[str, ...]
    execution_kind: Literal["read", "mutation"] = "read"
    side_effects: tuple[str, ...] = ()

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
        if self.runtime_requirements is not None and not issubclass(
            self.request_type, RuntimeRequest
        ):
            raise ValueError(
                f"Runtime Operation Request must extend RuntimeRequest: {command}"
            )
        if (
            self.runtime_requirements is not None
            and "runtime_incompatible" not in self.failure_codes
        ):
            raise ValueError(
                f"Runtime Operation must declare runtime_incompatible: {command}"
            )

    @property
    def cli_flags(self) -> dict[str, str]:
        return COMMON_CLI_FLAGS | (RUNTIME_CLI_FLAGS if self.requires_runtime else {})

    @property
    def requires_runtime(self) -> bool:
        return self.runtime_requirements is not None

    def schema(self) -> OperationSchema:
        command = f"spa {self.name}"
        return OperationSchema(
            operation=command,
            execution_kind=self.execution_kind,
            determinism="deterministic",
            side_effects=list(self.side_effects),
            minimum_aseprite_version=None,
            requires_runtime=self.requires_runtime,
            runtime_requirements=self.runtime_requirements,
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
