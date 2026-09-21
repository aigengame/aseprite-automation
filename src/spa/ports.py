"""Inner-owned facts exchanged with the Aseprite Runtime Integration adapter."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from spa.contracts import (
    Diagnostics,
    ProbePrerequisite,
    RuntimeCapability,
    RuntimeRequest,
)


@dataclass(frozen=True)
class RuntimeObservation:
    selection_source: Literal["explicit", "environment", "path"]
    requested_path: str | None
    discovered_path: str
    canonical_path: str
    resource_path: str
    aseprite_version: str
    api_version: int
    lua_version: str
    verified_prerequisites: tuple[ProbePrerequisite, ...]
    verified_capabilities: tuple[RuntimeCapability, ...]


RuntimeProbe = Callable[[RuntimeRequest], RuntimeObservation]


@dataclass(frozen=True)
class PackagedHandler:
    """Opaque packaged-resource identity selected by a Domain Module."""

    resource_name: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.resource_name):
            raise ValueError("Packaged handler name must be lower_snake_case")


@dataclass(frozen=True)
class KernelInvocationResult:
    payload: dict[str, Any]
    response_path: str
    diagnostics: Diagnostics


KernelInvoker = Callable[
    [RuntimeObservation, PackagedHandler, dict[str, Any], float],
    KernelInvocationResult,
]


@dataclass(frozen=True)
class TargetCommitObservation:
    target_sprite_file: str
    byte_size: int
    sha256: str


class TargetFiles(Protocol):
    """Domain-neutral staging and atomic Target Commit boundary."""

    def staged_path(self, target: Path) -> Path: ...

    def commit(self, staged: Path, target: Path) -> TargetCommitObservation: ...

    def discard(self, staged: Path) -> None: ...


@dataclass(frozen=True)
class OperationServices:
    probe_runtime: RuntimeProbe
    invoke_kernel: KernelInvoker
    target_files: TargetFiles


@dataclass(frozen=True)
class DiscoveryEvidence:
    requested_path: str | None
    searched: list[str]


@dataclass(frozen=True)
class ResourceEvidence:
    canonical_path: str
    searched: list[str]


@dataclass(frozen=True)
class LaunchEvidence:
    executable: str


@dataclass(frozen=True)
class ProcessEvidence:
    executable: str
    exit_status: int


@dataclass(frozen=True)
class ResponseEvidence:
    response_path: str


@dataclass(frozen=True)
class HandlerEvidence:
    response_path: str
    reason: str


@dataclass(frozen=True)
class PostconditionEvidence:
    response_path: str
    reason: str


@dataclass(frozen=True)
class RuntimeCompatibilityEvidence:
    aseprite_version: str
    lua_version: str
    api_version: int
    required_lua_language: str
    minimum_api_version: int
    missing_capabilities: tuple[RuntimeCapability, ...]


@dataclass(frozen=True)
class TargetCommitEvidence:
    target_sprite_file: str
    reason: Literal[
        "target_not_file",
        "staged_file_missing",
        "staged_file_empty",
        "replace_failed",
    ]


RuntimeEvidence = (
    DiscoveryEvidence
    | ResourceEvidence
    | LaunchEvidence
    | ProcessEvidence
    | ResponseEvidence
    | HandlerEvidence
    | PostconditionEvidence
    | RuntimeCompatibilityEvidence
    | TargetCommitEvidence
)
RuntimeIssueKind = Literal[
    "discovery_absent",
    "resources_absent",
    "launch_failed",
    "deadline",
    "output_overflow",
    "process_failed",
    "response_absent",
    "response_malformed",
    "handler_rejected",
    "postcondition_failed",
    "exit_mismatch",
    "runtime_incompatible",
    "target_commit_failed",
]
_EVIDENCE_TYPES: dict[RuntimeIssueKind, type[RuntimeEvidence]] = {
    "discovery_absent": DiscoveryEvidence,
    "resources_absent": ResourceEvidence,
    "launch_failed": LaunchEvidence,
    "deadline": ProcessEvidence,
    "output_overflow": ProcessEvidence,
    "process_failed": ProcessEvidence,
    "response_absent": ResponseEvidence,
    "response_malformed": ResponseEvidence,
    "handler_rejected": HandlerEvidence,
    "postcondition_failed": PostconditionEvidence,
    "exit_mismatch": ProcessEvidence,
    "runtime_incompatible": RuntimeCompatibilityEvidence,
    "target_commit_failed": TargetCommitEvidence,
}


class RuntimeIssue(Exception):
    """Technical failure evidence; Application chooses the public classification."""

    def __init__(
        self,
        kind: RuntimeIssueKind,
        message: str,
        evidence: RuntimeEvidence,
        diagnostics: Diagnostics | None = None,
    ):
        expected = _EVIDENCE_TYPES.get(kind)
        if expected is None or not isinstance(evidence, expected):
            raise TypeError(f"Invalid private evidence for runtime issue {kind}")
        super().__init__(message)
        self.kind = kind
        self.evidence = evidence
        self.diagnostics = diagnostics or Diagnostics()
