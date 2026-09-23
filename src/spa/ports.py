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
from spa.mutation import TargetCommitFailureReason


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
class PackagedResource:
    """One packaged Kernel resource and its private script parameter."""

    parameter_name: str
    package_name: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.parameter_name):
            raise ValueError("Packaged resource parameter must be lower_snake_case")
        if not re.fullmatch(r"[a-z][a-z0-9_]*\.(?:lua|aseprite)", self.package_name):
            raise ValueError("Packaged resource must be a Lua or Aseprite file name")


@dataclass(frozen=True)
class PackagedHandler:
    """Opaque packaged-resource identity selected by a Domain Module."""

    resource_name: str
    support_resources: tuple[PackagedResource, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.resource_name):
            raise ValueError("Packaged handler name must be lower_snake_case")
        parameters = [resource.parameter_name for resource in self.support_resources]
        if len(parameters) != len(set(parameters)):
            raise ValueError("Packaged resource parameters must be unique")


@dataclass(frozen=True)
class KernelInvocationResult:
    payload: dict[str, Any]
    response_path: str
    diagnostics: Diagnostics


KernelInvoker = Callable[
    [RuntimeObservation, PackagedHandler, dict[str, Any], float],
    KernelInvocationResult,
]
DirectKernelInvoker = Callable[
    [RuntimeRequest, PackagedHandler, dict[str, Any], float],
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

    def commit(
        self, staged: Path, target: Path, *, overwrite: bool
    ) -> TargetCommitObservation: ...

    def discard(self, staged: Path) -> None: ...


@dataclass(frozen=True)
class ArtifactFileObservation:
    path: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class StagedArtifact:
    payload: bytes
    byte_size: int
    sha256: str


class ArtifactFiles(Protocol):
    """Domain-neutral staging and publication of one Export Destination."""

    def normalize_destination(self, path: str) -> Path: ...

    def staged_path(self, destination: Path, *, if_exists: str) -> Path: ...

    def rendered_path(self, staged: Path) -> Path: ...

    def read_staged(self, staged: Path) -> StagedArtifact: ...

    def publish(
        self, staged: Path, destination: Path, *, if_exists: str, sha256: str
    ) -> ArtifactFileObservation: ...

    def discard(self, staged: Path) -> None: ...


@dataclass(frozen=True)
class PngFacts:
    width: int
    height: int
    color_profile: Literal["none", "srgb"]
    alpha_channel_present: bool
    alpha_min: int
    alpha_max: int
    rgba_bytes: bytes


PngVerifier = Callable[[bytes, Path], PngFacts]


@dataclass(frozen=True)
class OperationServices:
    probe_runtime: RuntimeProbe
    invoke_kernel: KernelInvoker
    target_files: TargetFiles
    artifact_files: ArtifactFiles | None = None
    verify_png: PngVerifier | None = None
    invoke_kernel_direct: DirectKernelInvoker | None = None


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
    failed_step: int | None = None
    failed_operation: str | None = None


@dataclass(frozen=True)
class HandlerEvidence:
    response_path: str
    reason: str
    failed_step: int | None = None
    failed_operation: str | None = None


@dataclass(frozen=True)
class PostconditionEvidence:
    response_path: str
    reason: str
    failed_step: int | None = None
    failed_operation: str | None = None


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
    reason: TargetCommitFailureReason


ArtifactFileFailureReason = Literal[
    "destination_exists",
    "destination_not_file",
    "destination_parent_missing",
    "staged_file_missing",
    "staged_file_empty",
    "staged_file_changed",
    "publication_failed",
]


@dataclass(frozen=True)
class ArtifactFileEvidence:
    path: str
    reason: ArtifactFileFailureReason


@dataclass(frozen=True)
class ArtifactVerificationEvidence:
    path: str
    reason: str


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
    | ArtifactFileEvidence
    | ArtifactVerificationEvidence
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
    "artifact_file_failed",
    "artifact_verification_failed",
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
    "artifact_file_failed": ArtifactFileEvidence,
    "artifact_verification_failed": ArtifactVerificationEvidence,
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
