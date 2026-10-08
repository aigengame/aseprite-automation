"""Inner-owned facts exchanged with the Aseprite Runtime Integration adapter."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import ConfigDict

from spa.contracts.artifact_set import ArtifactSets
from spa.contracts.caller_script import CallerScriptInvoker, ScriptFileObserver
from spa.contracts.encoded_animation import GifDecoder, SequencePngDecoder
from spa.contracts.mutation import (
    PublicationIdentityObserver,
    TargetCommitFailureReason,
)
from spa.contracts.public import (
    ConvolutionDiscovery,
    Diagnostics,
    ProbePrerequisite,
    PublicModel,
    RuntimeCapability,
    RuntimeRequest,
    ValidationIssue,
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
    convolution: ConvolutionDiscovery | None = None


RuntimeProbe = Callable[[RuntimeRequest], RuntimeObservation]

_PACKAGE_STEM = r"(?:[a-z][a-z0-9_]*/)*[a-z][a-z0-9_]*"


@dataclass(frozen=True)
class PackagedResource:
    """A Kernel-relative path bound to a semantic private script parameter."""

    parameter_name: str
    package_path: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.parameter_name):
            raise ValueError("Packaged resource parameter must be lower_snake_case")
        if not re.fullmatch(
            _PACKAGE_STEM + r"\.(?:lua|aseprite|icc|json)", self.package_path
        ):
            raise ValueError(
                "Packaged resource must be a relative Lua, Aseprite, ICC, or JSON path"
            )


@dataclass(frozen=True)
class PackagedHandler:
    """A logical handler identity and explicit Kernel-relative script path."""

    name: str
    package_path: str
    support_resources: tuple[PackagedResource, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.name):
            raise ValueError("Packaged handler name must be lower_snake_case")
        if not re.fullmatch(_PACKAGE_STEM + r"\.lua", self.package_path):
            raise ValueError("Packaged handler must be a relative Lua path")
        parameters = [resource.parameter_name for resource in self.support_resources]
        if len(parameters) != len(set(parameters)):
            raise ValueError("Packaged resource parameters must be unique")


@dataclass(frozen=True)
class KernelInvocationResult:
    payload: dict[str, Any]
    response_path: str
    diagnostics: Diagnostics


class KernelInvoker(Protocol):
    def __call__(
        self,
        observation: RuntimeObservation,
        handler: PackagedHandler,
        payload: dict[str, Any],
        timeout_seconds: float,
        /,
        *,
        working_directory: Path | None = None,
    ) -> KernelInvocationResult: ...


DirectKernelInvoker = Callable[
    [RuntimeRequest, PackagedHandler, dict[str, Any], float],
    KernelInvocationResult,
]


@dataclass(frozen=True)
class TargetCommitObservation:
    target_sprite_file: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class PathObservation:
    exists: bool
    is_file: bool
    parent_is_dir: bool


class TargetFiles(PublicationIdentityObserver, Protocol):
    """Domain-neutral staging and atomic Target Commit boundary."""

    def observe_path(self, path: Path) -> PathObservation: ...

    def staged_path(self, target: Path) -> Path: ...

    def stage_copy(self, source: Path, staged: Path) -> None: ...

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


@dataclass(frozen=True)
class ArtifactPublication:
    role: str
    staged: Path
    destination: Path
    if_exists: Literal["fail", "replace"]
    sha256: str


class PublishedArtifactDestination(PublicModel):
    model_config = ConfigDict(frozen=True)

    role: str
    path: str
    existed_before: bool
    state: Literal["published"]
    replaced_existing: bool


class UnpublishedArtifactDestination(PublicModel):
    model_config = ConfigDict(frozen=True)

    role: str
    path: str
    existed_before: bool
    state: Literal["not_published", "indeterminate"]
    replaced_existing: None = None


ArtifactDestinationState = PublishedArtifactDestination | UnpublishedArtifactDestination


@dataclass(frozen=True)
class PartialPublicationEvidence:
    destinations: tuple[ArtifactDestinationState, ...]


class ArtifactFiles(Protocol):
    """Domain-neutral staging and publication of one Export Destination."""

    def normalize_destination(self, path: str) -> Path: ...

    def read_input(self, path: Path) -> bytes: ...

    def ensure_source_separate(self, source: Path, destination: Path) -> None: ...

    def destination_exists(self, destination: Path) -> bool: ...

    def staged_path(self, destination: Path, *, if_exists: str) -> Path: ...

    def ensure_destinations_distinct(self, destinations: tuple[Path, ...]) -> None: ...

    def publish_many(
        self, artifacts: tuple[ArtifactPublication, ...]
    ) -> tuple[ArtifactFileObservation, ...]: ...

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
    color_profile: Literal["none", "srgb", "icc"]
    alpha_channel_present: bool
    alpha_min: int
    alpha_max: int
    rgba_bytes: bytes


PngVerifier = Callable[[bytes, Path], PngFacts]


@dataclass(frozen=True)
class PngRasterFacts:
    width: int
    height: int
    color_mode: Literal["rgb", "grayscale", "indexed"]
    rgba_bytes: bytes
    stored_bytes: bytes
    entries: tuple[tuple[int, int, int, int], ...]
    color_profile: Literal["none", "srgb", "icc"]
    icc_bytes: bytes | None
    color_type: int | None = None
    srgb_rendering_intent: int | None = None


@dataclass(frozen=True)
class PngInputFacts(PngRasterFacts):
    color_mode: Literal["rgb", "indexed"]


PngArtifactDecoder = Callable[[bytes], PngRasterFacts]


class PngInputError(ValueError):
    """The bytes do not represent a supported, valid raster input PNG."""


PngInputDecoder = Callable[[bytes], PngInputFacts]


@dataclass(frozen=True)
class IccFacts:
    byte_size: int
    sha256: str
    color_space: str


class IccVerificationError(ValueError):
    """The input bytes are not a valid ICC profile."""


IccVerifier = Callable[[bytes], IccFacts]


@dataclass(frozen=True)
class PaletteFileFacts:
    entries: tuple[tuple[int, int, int, int], ...]
    byte_size: int
    sha256: str


class PaletteFileError(ValueError):
    """The bytes do not represent the requested Palette file format."""


PaletteFileDecoder = Callable[[bytes, Literal["gpl", "png"]], PaletteFileFacts]


@dataclass(frozen=True)
class OperationServices:
    probe_runtime: RuntimeProbe
    invoke_kernel: KernelInvoker
    target_files: TargetFiles
    artifact_files: ArtifactFiles | None = None
    verify_png: PngVerifier | None = None
    verify_icc: IccVerifier | None = None
    invoke_kernel_direct: DirectKernelInvoker | None = None
    decode_palette_file: PaletteFileDecoder | None = None
    decode_png_input: PngInputDecoder | None = None
    artifact_sets: ArtifactSets | None = None
    decode_sequence_png: SequencePngDecoder | None = None
    decode_gif: GifDecoder | None = None
    decode_png_artifact: PngArtifactDecoder | None = None
    invoke_script: CallerScriptInvoker | None = None
    observe_script_file: ScriptFileObserver | None = None


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
    "input_file_unreadable",
    "source_destination_alias",
    "destination_collision",
    "source_destination_identity_unverified",
    "destination_exists",
    "destination_not_file",
    "destination_parent_missing",
    "staged_file_missing",
    "staged_file_empty",
    "staged_file_changed",
    "publication_failed",
    "destination_set_empty",
    "destination_invalid",
    "staging_failed",
    "staged_set_mismatch",
    "staged_file_not_regular",
    "staged_set_unreadable",
    "destination_unreadable",
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
    | PartialPublicationEvidence
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
    "partial_publication",
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
    "partial_publication": PartialPublicationEvidence,
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


class RequestIssue(Exception):
    """Statically detected request failure after schema validation."""

    def __init__(self, issues: list[ValidationIssue]):
        super().__init__("Invalid Operation Request")
        self.issues = issues


class OperationIssue(Exception):
    """Dynamic domain refusal with a registered public Failure Code."""

    def __init__(self, code: str, message: str, details: PublicModel):
        super().__init__(message)
        self.code = code
        self.details = details
