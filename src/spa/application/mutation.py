"""Completion of validated standalone Sprite mutations."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path

from spa.contracts.mutation import TargetCommit, source_target_identity_issue
from spa.contracts.ports import (
    RequestIssue,
    RuntimeIssue,
    TargetCommitEvidence,
    TargetFiles,
)


@dataclass(frozen=True)
class _MutationCompletion:
    staged_sprite_file: Path
    _files: TargetFiles
    _source: Path
    _target: Path
    _in_place: bool
    _overwrite: bool
    _identity_change_message: str

    def commit(self) -> TargetCommit:
        """Publish only after the caller has validated native evidence."""
        issue = source_target_identity_issue(
            self._files, self._source, self._target, self._in_place
        )
        if issue is not None:
            raise RuntimeIssue(
                "target_commit_failed",
                self._identity_change_message,
                TargetCommitEvidence(
                    str(self._target), "source_target_identity_changed"
                ),
            )
        committed = self._files.commit(
            self.staged_sprite_file, self._target, overwrite=self._overwrite
        )
        return TargetCommit(
            target_sprite_file=committed.target_sprite_file,
            byte_size=committed.byte_size,
            sha256=committed.sha256,
        )


def prepare_mutation(
    files: TargetFiles,
    source: Path,
    target: Path,
    *,
    in_place: bool,
    overwrite: bool,
    identity_change_message: str,
) -> AbstractContextManager[_MutationCompletion]:
    """Check identity now; own staging and cleanup when the caller enters."""
    issue = source_target_identity_issue(files, source, target, in_place)
    if issue is not None:
        raise RequestIssue([issue])
    return _staged_mutation(
        files, source, target, in_place, overwrite, identity_change_message
    )


@contextmanager
def _staged_mutation(
    files: TargetFiles,
    source: Path,
    target: Path,
    in_place: bool,
    overwrite: bool,
    identity_change_message: str,
) -> Iterator[_MutationCompletion]:
    staged = files.staged_path(target)
    try:
        yield _MutationCompletion(
            staged, files, source, target, in_place, overwrite, identity_change_message
        )
    finally:
        files.discard(staged)
