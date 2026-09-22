"""Local filesystem adapter for staged Sprite publication."""

import hashlib
import os
import uuid
from pathlib import Path

from spa.ports import RuntimeIssue, TargetCommitEvidence, TargetCommitObservation


class LocalTargetFiles:
    def staged_path(self, target: Path) -> Path:
        token = uuid.uuid4().hex
        return target.with_name(f".{target.stem}.{token}.staged.aseprite")

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
