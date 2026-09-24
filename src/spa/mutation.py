"""Shared Source/Target intent and Target Commit contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from spa.contracts import FailureCodeSpec, PublicModel, ValidationIssue


def validate_native_sprite_path(value: str) -> str:
    if Path(value).suffix.lower() != ".aseprite":
        raise ValueError("Sprite file must use the .aseprite extension")
    return value


def require_overwrite_for_in_place(in_place: bool, overwrite: bool) -> None:
    if in_place and not overwrite:
        raise ValueError("in_place requires overwrite permission")


class PublicationIdentityObserver(Protocol):
    def same_publication_entry(self, source: Path, target: Path) -> bool: ...

    def same_publication_target(self, source: Path, target: Path) -> bool: ...


def source_target_identity_issue(
    files: PublicationIdentityObserver, source: Path, target: Path, in_place: bool
) -> ValidationIssue | None:
    try:
        same_entry = files.same_publication_entry(source, target)
        traverses_target = not same_entry and files.same_publication_target(
            source, target
        )
    except OSError:
        return ValidationIssue(
            location=["source_sprite_file"],
            code="source_target_identity",
            message="Source/Target publication identity could not be verified",
        )
    if traverses_target:
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
