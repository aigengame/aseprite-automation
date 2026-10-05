"""Scoped publication of one domain-validated JSON Snapshot Artifact."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from spa.contracts.ports import ArtifactFileObservation, ArtifactFiles
from spa.contracts.snapshot import SnapshotDestination


@dataclass
class StagedSnapshot:
    """Bind publication to the bytes accepted by the Snapshot's domain owner."""

    path: Path
    _source: Path
    _destination: Path
    _intent: SnapshotDestination
    _files: ArtifactFiles
    _verified_sha256: str | None = field(default=None, init=False)

    def verify[T](self, validate: Callable[[bytes], T]) -> T:
        """Read once, then let the owner validate and classify its Snapshot."""
        self._verified_sha256 = None
        contents = self._files.read_staged(self.path)
        value = validate(contents.payload)
        self._verified_sha256 = contents.sha256
        return value

    def publish(self) -> ArtifactFileObservation:
        """Recheck Source separation and publish only the verified bytes."""
        if self._verified_sha256 is None:
            raise RuntimeError("Snapshot must pass verification before publication")
        self._files.ensure_source_separate(self._source, self._destination)
        return self._files.publish(
            self.path,
            self._destination,
            if_exists=self._intent.if_exists,
            sha256=self._verified_sha256,
        )


@contextmanager
def staged_snapshot(
    files: ArtifactFiles | None,
    *,
    source: Path,
    destination: SnapshotDestination | None,
) -> Iterator[StagedSnapshot | None]:
    """Own staging and cleanup; inline and summary reads need no File Adapter."""
    if destination is None:
        yield None
        return
    assert files is not None
    normalized = files.normalize_destination(destination.path)
    files.ensure_source_separate(source, normalized)
    path = files.staged_path(normalized, if_exists=destination.if_exists)
    staged = StagedSnapshot(path, source, normalized, destination, files)
    try:
        yield staged
    finally:
        staged._verified_sha256 = None
        files.discard(path)
