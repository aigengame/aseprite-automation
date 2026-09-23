"""Shared Source/Target intent and Target Commit contracts."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from spa.contracts import FailureCodeSpec, PublicModel, ValidationIssue

if TYPE_CHECKING:
    from spa.ports import TargetFiles


def source_target_identity_issue(
    files: TargetFiles, source: Path, target: Path, in_place: bool
) -> ValidationIssue | None:
    same_entry = files.same_publication_entry(source, target)
    if not same_entry and files.same_publication_target(source, target):
        return ValidationIssue(
            location=["source_sprite_file"],
            code="source_target_identity",
            message="Source alias traverses the Target publication entry",
        )
    if same_entry != in_place:
        return ValidationIssue(
            location=["in_place"],
            code="source_target_identity",
            message="Source/Target publication identity must match in_place intent",
        )
    return None


class TargetCommit(PublicModel):
    target_sprite_file: str
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


TargetCommitFailureReason = Literal[
    "target_not_file",
    "overwrite_not_allowed",
    "staged_file_missing",
    "staged_file_empty",
    "replace_failed",
    "source_target_identity_changed",
]


class TargetCommitDetails(PublicModel):
    kind: Literal["target_commit"] = "target_commit"
    target_sprite_file: str
    reason: TargetCommitFailureReason


MUTATION_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "target_commit_failed",
        "The validated staged Sprite could not be published at its declared target",
        "execution",
        TargetCommitDetails,
    ),
)
