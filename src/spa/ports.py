"""Inner-owned facts exchanged with the Aseprite Runtime Integration adapter."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from spa.contracts import Diagnostics, RuntimeCapability, RuntimeRequest


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
    verified_capabilities: tuple[RuntimeCapability, ...]


RuntimeProbe = Callable[[RuntimeRequest], RuntimeObservation]


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
class RuntimeCompatibilityEvidence:
    aseprite_version: str
    lua_version: str
    api_version: int
    required_lua_language: str
    minimum_api_version: int
    missing_capabilities: tuple[RuntimeCapability, ...]


RuntimeEvidence = (
    DiscoveryEvidence
    | ResourceEvidence
    | LaunchEvidence
    | ProcessEvidence
    | ResponseEvidence
    | HandlerEvidence
    | RuntimeCompatibilityEvidence
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
    "exit_mismatch",
    "runtime_incompatible",
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
    "exit_mismatch": ProcessEvidence,
    "runtime_incompatible": RuntimeCompatibilityEvidence,
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
