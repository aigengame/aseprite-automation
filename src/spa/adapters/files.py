"""Local filesystem adapter for staged Sprite publication."""

import hashlib
import os
import shutil
import uuid
from pathlib import Path

from spa.contracts.ports import (
    ArtifactFileEvidence,
    ArtifactFileObservation,
    PathObservation,
    RuntimeIssue,
    StagedArtifact,
    TargetCommitEvidence,
    TargetCommitObservation,
)


def _publication_entry(path: Path) -> Path:
    return path.parent.resolve() / path.name


def _same_publication_entry(source: Path, target: Path) -> bool:
    """Compare entries, including alternate spellings on insensitive filesystems."""
    source_entry = _publication_entry(source)
    target_entry = _publication_entry(target)
    if source_entry == target_entry:
        return True
    try:
        if not source_entry.parent.samefile(target_entry.parent):
            return False
    except (FileNotFoundError, NotADirectoryError):
        return False
    if source_entry.name == target_entry.name:
        return True
    try:
        if not os.path.samestat(source_entry.lstat(), target_entry.lstat()):
            return False
    except (FileNotFoundError, NotADirectoryError):
        return False
    names = set(os.listdir(source_entry.parent))
    # Hard links can share an inode while remaining separate directory entries.
    return not (source_entry.name in names and target_entry.name in names)


def _same_publication_target(source: Path, target: Path) -> bool:
    """Whether replacing the Target entry changes reads through Source."""
    target_entry = _publication_entry(target)
    source_entry = _publication_entry(source)
    visited: set[Path] = set()
    while source_entry not in visited:
        if _same_publication_entry(source_entry, target_entry):
            return True
        visited.add(source_entry)
        if not source_entry.is_symlink():
            return False
        linked = source_entry.parent / source_entry.readlink()
        source_entry = _publication_entry(linked)
    return False


class LocalTargetFiles:
    def observe_path(self, path: Path) -> PathObservation:
        return PathObservation(
            exists=path.exists() or path.is_symlink(),
            is_file=path.is_file(),
            parent_is_dir=path.parent.is_dir(),
        )

    def same_publication_entry(self, source: Path, target: Path) -> bool:
        """Whether Source and Target name the same entry replaced by Target Commit."""
        return _same_publication_entry(source, target)

    def same_publication_target(self, source: Path, target: Path) -> bool:
        """Whether replacing the Target entry changes reads through Source."""
        return _same_publication_target(source, target)

    def staged_path(self, target: Path) -> Path:
        token = uuid.uuid4().hex
        return target.with_name(f".{target.stem}.{token}.staged.aseprite")

    def stage_copy(self, source: Path, staged: Path) -> None:
        shutil.copyfile(source, staged)

    def commit(
        self, staged: Path, target: Path, *, overwrite: bool
    ) -> TargetCommitObservation:
        if target.exists() and not target.is_file():
            raise RuntimeIssue(
                "target_commit_failed",
                "Target Sprite File exists but is not a regular file",
                TargetCommitEvidence(str(target), "target_not_file"),
            )
        if target.is_file() and not overwrite:
            raise RuntimeIssue(
                "target_commit_failed",
                "Target Sprite File already exists and overwrite is false",
                TargetCommitEvidence(str(target), "overwrite_not_allowed"),
            )
        if not staged.is_file():
            raise RuntimeIssue(
                "target_commit_failed",
                "Kernel did not produce a staged Sprite file",
                TargetCommitEvidence(str(target), "staged_file_missing"),
            )
        try:
            payload = staged.read_bytes()
        except OSError as exc:
            raise RuntimeIssue(
                "target_commit_failed",
                "Staged Sprite file could not be read",
                TargetCommitEvidence(str(target), "staged_file_missing"),
            ) from exc
        if not payload:
            raise RuntimeIssue(
                "target_commit_failed",
                "Kernel produced an empty staged Sprite file",
                TargetCommitEvidence(str(target), "staged_file_empty"),
            )
        digest = hashlib.sha256(payload).hexdigest()
        byte_size = len(payload)
        try:
            if overwrite:
                os.replace(staged, target)
            else:
                os.link(staged, target)
        except FileExistsError as exc:
            raise RuntimeIssue(
                "target_commit_failed",
                "Target Sprite File appeared before publication and overwrite is false",
                TargetCommitEvidence(str(target), "overwrite_not_allowed"),
            ) from exc
        except OSError as exc:
            raise RuntimeIssue(
                "target_commit_failed",
                "Staged Sprite file could not be published at the declared target",
                TargetCommitEvidence(str(target), "replace_failed"),
            ) from exc
        return TargetCommitObservation(
            target_sprite_file=str(target),
            byte_size=byte_size,
            sha256=digest,
        )

    def discard(self, staged: Path) -> None:
        try:
            staged.unlink()
        except OSError:
            pass


class LocalArtifactFiles:
    """File mechanics for verified Export Destinations."""

    def normalize_destination(self, path: str) -> Path:
        return Path(os.path.abspath(os.path.expanduser(path)))

    def read_input(self, path: Path) -> bytes:
        try:
            return path.expanduser().read_bytes()
        except (OSError, ValueError, RuntimeError) as exc:
            raise RuntimeIssue(
                "artifact_file_failed",
                "Input Artifact could not be read",
                ArtifactFileEvidence(str(path), "input_file_unreadable"),
            ) from exc

    def ensure_source_separate(self, source: Path, destination: Path) -> None:
        try:
            # Match read_input's expansion before comparing publication entries.
            aliases_source = _same_publication_target(source.expanduser(), destination)
        except (OSError, ValueError, RuntimeError) as exc:
            raise RuntimeIssue(
                "artifact_file_failed",
                "Source/Destination publication identity could not be verified",
                ArtifactFileEvidence(
                    str(destination), "source_destination_identity_unverified"
                ),
            ) from exc
        if aliases_source:
            raise RuntimeIssue(
                "artifact_file_failed",
                "Export Destination would replace the Source Sprite File",
                ArtifactFileEvidence(str(destination), "source_destination_alias"),
            )

    def staged_path(self, destination: Path, *, if_exists: str) -> Path:
        if not destination.parent.is_dir():
            raise RuntimeIssue(
                "artifact_file_failed",
                "Export Destination parent directory does not exist",
                ArtifactFileEvidence(str(destination), "destination_parent_missing"),
            )
        if destination.exists() or destination.is_symlink():
            if not destination.is_file() or destination.is_symlink():
                raise RuntimeIssue(
                    "artifact_file_failed",
                    "Export Destination is not a regular file",
                    ArtifactFileEvidence(str(destination), "destination_not_file"),
                )
            if if_exists == "fail":
                raise RuntimeIssue(
                    "artifact_file_failed",
                    "Export Destination already exists",
                    ArtifactFileEvidence(str(destination), "destination_exists"),
                )
        return destination.with_name(
            f".{destination.stem}.{uuid.uuid4().hex}.staged{destination.suffix}"
        )

    def destination_exists(self, destination: Path) -> bool:
        """Observe a publication entry without hiding an inaccessible parent."""
        try:
            destination.lstat()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise RuntimeIssue(
                "artifact_file_failed",
                "Export Destination existence could not be observed",
                ArtifactFileEvidence(str(destination), "publication_failed"),
            ) from exc
        return True

    def rendered_path(self, staged: Path) -> Path:
        return staged.with_suffix(".rgba")

    def read_staged(self, staged: Path) -> StagedArtifact:
        try:
            payload = staged.read_bytes()
        except OSError as exc:
            raise RuntimeIssue(
                "artifact_file_failed",
                "Native encoder did not produce a readable staged Artifact",
                ArtifactFileEvidence(str(staged), "staged_file_missing"),
            ) from exc
        if not payload:
            raise RuntimeIssue(
                "artifact_file_failed",
                "Native encoder produced an empty staged Artifact",
                ArtifactFileEvidence(str(staged), "staged_file_empty"),
            )
        return StagedArtifact(
            payload, len(payload), hashlib.sha256(payload).hexdigest()
        )

    def publish(
        self, staged: Path, destination: Path, *, if_exists: str, sha256: str
    ) -> ArtifactFileObservation:
        staged_artifact = self.read_staged(staged)
        if staged_artifact.sha256 != sha256:
            raise RuntimeIssue(
                "artifact_file_failed",
                "Staged Artifact changed after verification",
                ArtifactFileEvidence(str(destination), "staged_file_changed"),
            )
        try:
            if if_exists == "replace":
                if destination.exists() and not destination.is_file():
                    raise IsADirectoryError(str(destination))
                os.replace(staged, destination)
            else:
                os.link(staged, destination)
        except FileExistsError as exc:
            raise RuntimeIssue(
                "artifact_file_failed",
                "Export Destination appeared before publication",
                ArtifactFileEvidence(str(destination), "destination_exists"),
            ) from exc
        except OSError as exc:
            raise RuntimeIssue(
                "artifact_file_failed",
                "Staged Artifact could not be published",
                ArtifactFileEvidence(str(destination), "publication_failed"),
            ) from exc
        return ArtifactFileObservation(
            str(destination), staged_artifact.byte_size, sha256
        )

    def discard(self, staged: Path) -> None:
        try:
            staged.unlink()
        except OSError:
            pass
