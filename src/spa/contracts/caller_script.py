"""Caller-script transport contract, separate from native domain Operations."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import Field, field_validator

from spa.contracts.public import Diagnostics, PublicModel, RuntimeRequest

if TYPE_CHECKING:
    from spa.contracts.ports import RuntimeObservation


PathText = Annotated[str, Field(min_length=1, pattern=r"^[^\x00]+$")]
ParameterName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
ParameterValue = Annotated[str, Field(pattern=r"^[^\x00]*$")]


class InlineScript(PublicModel):
    kind: Literal["inline"]
    code: str

    @field_validator("code")
    @classmethod
    def valid_utf8(cls, value: str) -> str:
        value.encode("utf-8")
        return value


class FileScript(PublicModel):
    kind: Literal["file"]
    path: PathText


class ScriptRunRequest(RuntimeRequest):
    script: Annotated[InlineScript | FileScript, Field(discriminator="kind")]
    parameters: dict[ParameterName, ParameterValue] = Field(default_factory=dict)
    working_directory: PathText | None = None
    declared_files: list[PathText] = Field(default_factory=list)


class ScriptFileFact(PublicModel):
    path: str
    kind: Literal["file", "directory", "other", "missing", "unavailable"]
    size_bytes: int | None = Field(default=None, ge=0)
    error: str | None = None


class ScriptSuccessDiagnostics(Diagnostics):
    exit_status: Literal[0] = Field(...)


class ScriptRunResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa script run"] = "spa script run"
    execution_kind: Literal["script-run"] = "script-run"
    determinism: Literal["caller-defined"] = "caller-defined"
    executable: str
    working_directory: str
    timeout_seconds: float = Field(gt=0, le=120)
    output_limit_bytes: int = Field(ge=1)
    diagnostics: ScriptSuccessDiagnostics
    files: list[ScriptFileFact]


@dataclass(frozen=True)
class ScriptInvocationResult:
    executable: str
    working_directory: str
    output_limit_bytes: int
    diagnostics: Diagnostics
    files: tuple[ScriptFileFact, ...]


class CallerScriptInvoker(Protocol):
    def __call__(
        self, observation: "RuntimeObservation", request: ScriptRunRequest
    ) -> ScriptInvocationResult: ...
