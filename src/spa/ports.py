"""Inner-owned facts exchanged with the Aseprite Runtime Integration adapter."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from spa.contracts import Diagnostics, RuntimeRequest


@dataclass(frozen=True)
class RuntimeObservation:
    selection_source: Literal["explicit", "environment", "path"]
    requested_path: str | None
    discovered_path: str
    canonical_path: str
    resource_path: str
    aseprite_version: str
    api_version: int


RuntimeProbe = Callable[[RuntimeRequest], RuntimeObservation]
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
]


class RuntimeIssue(Exception):
    """Technical failure evidence; Application chooses the public classification."""

    def __init__(
        self,
        kind: RuntimeIssueKind,
        message: str,
        evidence: dict[str, Any],
        diagnostics: Diagnostics | None = None,
    ):
        super().__init__(message)
        self.kind = kind
        self.evidence = evidence
        self.diagnostics = diagnostics or Diagnostics()
