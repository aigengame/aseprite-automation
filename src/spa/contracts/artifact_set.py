"""Inner-owned file mechanics for bounded Export Destination sets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from spa.contracts.ports import ArtifactFileObservation, StagedArtifact


@dataclass(frozen=True)
class ArtifactDestination:
    role: str
    path: Path
    if_exists: Literal["fail", "replace"]


@dataclass(frozen=True)
class StagedArtifactSet:
    root: Path
    output_directory: Path
    evidence_directory: Path
    destinations: tuple[ArtifactDestination, ...]
    source: Path


@dataclass(frozen=True)
class ArtifactPublicationState:
    role: str
    path: str
    existed_before_publication: bool
    state: Literal["published", "not_published", "indeterminate"]
    replaced_existing: bool | None = None


class ArtifactSetPublicationError(Exception):
    """Known or indeterminate final changes prevent a successful Artifact set."""

    def __init__(
        self, message: str, destinations: tuple[ArtifactPublicationState, ...]
    ) -> None:
        super().__init__(message)
        self.destinations = destinations


class ArtifactSets(Protocol):
    def prepare(
        self, source: Path, destinations: tuple[ArtifactDestination, ...]
    ) -> StagedArtifactSet: ...

    def verify_set(self, staged: StagedArtifactSet) -> tuple[StagedArtifact, ...]: ...

    def publish(
        self, staged: StagedArtifactSet, sha256s: tuple[str, ...]
    ) -> tuple[ArtifactFileObservation, ...]: ...

    def discard(self, staged: StagedArtifactSet) -> None: ...
