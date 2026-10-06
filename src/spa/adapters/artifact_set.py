"""Local file mechanics for a bounded set of verified Export Destinations."""

import shutil
import stat
import tempfile
from dataclasses import replace
from pathlib import Path

from spa.adapters.files import LocalArtifactFiles, _same_publication_entry
from spa.contracts.artifact_set import (
    ArtifactDestination,
    ArtifactPublicationState,
    ArtifactSetPublicationError,
    StagedArtifactSet,
)
from spa.contracts.ports import (
    ArtifactFileEvidence,
    ArtifactFileFailureReason,
    ArtifactFileObservation,
    RuntimeIssue,
    StagedArtifact,
)


def _file_issue(
    path: Path, reason: ArtifactFileFailureReason, message: str
) -> RuntimeIssue:
    return RuntimeIssue(
        "artifact_file_failed", message, ArtifactFileEvidence(str(path), reason)
    )


def _entry_signature(path: Path) -> tuple[int, ...] | None:
    try:
        observation = path.lstat()
    except FileNotFoundError:
        return None
    return (
        observation.st_dev,
        observation.st_ino,
        observation.st_mode,
        observation.st_size,
        observation.st_mtime_ns,
        observation.st_ctime_ns,
    )


class LocalArtifactSets:
    def __init__(self, artifact_files: LocalArtifactFiles | None = None) -> None:
        self._files = artifact_files or LocalArtifactFiles()

    def prepare(
        self, source: Path, destinations: tuple[ArtifactDestination, ...]
    ) -> StagedArtifactSet:
        if not destinations:
            raise _file_issue(
                source, "destination_set_empty", "Export Destination set is empty"
            )
        root: Path | None = None
        try:
            normalized = tuple(
                replace(item, path=self._files.normalize_destination(str(item.path)))
                for item in destinations
            )
            names: set[str] = set()
            paths: list[Path] = []
            for item in normalized:
                if item.if_exists not in ("fail", "replace") or not item.role:
                    raise _file_issue(
                        item.path,
                        "destination_invalid",
                        "Export Destination intent is invalid",
                    )
                if item.path.name in names or any(
                    _same_publication_entry(previous, item.path) for previous in paths
                ):
                    raise _file_issue(
                        item.path,
                        "destination_collision",
                        "Export Destinations collide",
                    )
                names.add(item.path.name)
                paths.append(item.path)
                self._files.ensure_source_separate(source, item.path)
                self._files.staged_path(item.path, if_exists=item.if_exists)
            # Current exports share one destination directory. Keep native output
            # on that filesystem so the existing atomic link/replace can publish it.
            root = Path(
                tempfile.mkdtemp(
                    prefix=".spa-artifact-set-", dir=normalized[0].path.parent
                )
            )
            output = root / "outputs"
            evidence = root / "evidence"
            output.mkdir()
            evidence.mkdir()
            return StagedArtifactSet(root, output, evidence, normalized, source)
        except (OSError, ValueError, RuntimeError) as exc:
            if root is not None:
                shutil.rmtree(root, ignore_errors=True)
            raise _file_issue(
                source,
                "staging_failed",
                "Export Destination staging could not be prepared",
            ) from exc

    def verify_set(self, staged: StagedArtifactSet) -> tuple[StagedArtifact, ...]:
        try:
            entries = tuple(staged.output_directory.iterdir())
            expected = {item.path.name for item in staged.destinations}
            if {entry.name for entry in entries} != expected:
                raise _file_issue(
                    staged.output_directory,
                    "staged_set_mismatch",
                    "Native output does not match the complete declared Artifact set",
                )
            if any(not stat.S_ISREG(entry.lstat().st_mode) for entry in entries):
                raise _file_issue(
                    staged.output_directory,
                    "staged_file_not_regular",
                    "Native output contains a nonregular Artifact",
                )
        except OSError as exc:
            raise _file_issue(
                staged.output_directory,
                "staged_set_unreadable",
                "Native output set could not be inspected",
            ) from exc
        return tuple(
            self._files.read_staged(staged.output_directory / item.path.name)
            for item in staged.destinations
        )

    def publish(
        self, staged: StagedArtifactSet, sha256s: tuple[str, ...]
    ) -> tuple[ArtifactFileObservation, ...]:
        observations = self.verify_set(staged)
        if len(sha256s) != len(observations) or any(
            observation.sha256 != digest
            for observation, digest in zip(observations, sha256s)
        ):
            raise _file_issue(
                staged.output_directory,
                "staged_file_changed",
                "Staged Artifact set changed after verification",
            )
        try:
            states = [
                ArtifactPublicationState(
                    item.role,
                    str(item.path),
                    _entry_signature(item.path) is not None,
                    "not_published",
                )
                for item in staged.destinations
            ]
        except OSError as exc:
            raise _file_issue(
                staged.output_directory,
                "destination_unreadable",
                "Export Destinations could not be inspected before publication",
            ) from exc
        published: list[ArtifactFileObservation] = []
        for index, (item, digest) in enumerate(
            zip(staged.destinations, sha256s, strict=True)
        ):
            attempted = False
            before = None
            try:
                self._files.ensure_source_separate(staged.source, item.path)
                before = _entry_signature(item.path)
                states[index] = replace(
                    states[index], existed_before_publication=before is not None
                )
                attempted = True
                observation = self._files.publish(
                    staged.output_directory / item.path.name,
                    item.path,
                    if_exists=item.if_exists,
                    sha256=digest,
                )
            except (RuntimeIssue, OSError) as exc:
                if attempted:
                    try:
                        unchanged = _entry_signature(item.path) == before
                    except OSError:
                        unchanged = False
                    if not unchanged:
                        states[index] = replace(states[index], state="indeterminate")
                if any(state.state != "not_published" for state in states):
                    raise ArtifactSetPublicationError(
                        "Export Destination set could not be completely published",
                        tuple(states),
                    ) from exc
                if isinstance(exc, RuntimeIssue):
                    raise
                raise _file_issue(
                    item.path,
                    "publication_failed",
                    "Staged Artifact could not be published",
                ) from exc
            states[index] = replace(
                states[index],
                state="published",
                replaced_existing=before is not None,
            )
            published.append(observation)
        return tuple(published)

    def discard(self, staged: StagedArtifactSet) -> None:
        shutil.rmtree(staged.root, ignore_errors=True)
