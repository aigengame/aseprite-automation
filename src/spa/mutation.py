"""Shared contracts for staged Sprite mutation publication."""

from typing import Literal

from pydantic import Field

from spa.contracts import FailureCodeSpec, PublicModel


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
