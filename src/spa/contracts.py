"""Published Language models for the installed meta-operation slice."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Request(PublicModel):
    pass


class VersionRequest(Request):
    pass


class RuntimeRequest(Request):
    aseprite: str | None = Field(default=None, min_length=1)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class RuntimeFacts(PublicModel):
    selection_source: Literal["explicit", "environment", "path"]
    requested_path: str | None
    discovered_path: str
    canonical_path: str
    resource_complete: bool
    resource_path: str
    aseprite_version: str
    api_version: int


class CapabilityGap(PublicModel):
    capability: str
    aseprite_version: str
    evidence: str


class VersionResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa version"] = "spa version"
    spa_version: str


class InfoResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa info"] = "spa info"
    spa_version: str
    runtime: RuntimeFacts
    supported_capabilities: list[str]
    capability_gaps: list[CapabilityGap]


class OperationSchema(PublicModel):
    operation: str
    execution_kind: Literal["read"]
    determinism: Literal["deterministic"]
    side_effects: list[str]
    minimum_aseprite_version: str | None
    requires_runtime: bool
    request_schema: dict
    result_schema: dict
    failure_schema: dict
    invocation_schema: dict


class SchemaResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa schema"] = "spa schema"
    spa_version: str
    runtime: RuntimeFacts
    operations: list[OperationSchema]
    capability_gaps: list[CapabilityGap]


class NotFoundDetails(PublicModel):
    kind: Literal["executable_not_found"] = "executable_not_found"
    requested_path: str | None
    searched: list[str]


class ResourceDetails(PublicModel):
    kind: Literal["resource_incomplete"] = "resource_incomplete"
    canonical_path: str
    searched: list[str]


class ProcessDetails(PublicModel):
    kind: Literal["process"] = "process"
    executable: str
    exit_status: int | None = None


class ProtocolDetails(PublicModel):
    kind: Literal["protocol"] = "protocol"
    response_path: str
    protocol_version: int = 1


class KernelExecutionDetails(PublicModel):
    kind: Literal["kernel_execution"] = "kernel_execution"
    response_path: str
    reason: str


class RequestDetails(PublicModel):
    kind: Literal["invalid_request"] = "invalid_request"
    errors: list["ValidationIssue"]


class ValidationIssue(PublicModel):
    location: list[str | int]
    code: str
    message: str


FailureDetails = Annotated[
    NotFoundDetails
    | ResourceDetails
    | ProcessDetails
    | ProtocolDetails
    | KernelExecutionDetails
    | RequestDetails,
    Field(discriminator="kind"),
]


class Diagnostics(PublicModel):
    stdout: str = ""
    stderr: str = ""
    exit_status: int | None = None


class FailureEnvelope(PublicModel):
    status: Literal["failure"] = "failure"
    operation: str
    code: str
    category: Literal["input", "environment", "execution", "protocol"]
    message: str
    details: FailureDetails
    diagnostics: Diagnostics = Field(default_factory=Diagnostics)
