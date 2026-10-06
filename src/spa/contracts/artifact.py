"""Shared Artifact publication and verification failure details."""

from typing import Literal

from spa.contracts.ports import ArtifactDestinationState, ArtifactFileFailureReason
from spa.contracts.public import FailureCodeSpec, PublicModel


class ArtifactFileDetails(PublicModel):
    kind: Literal["artifact_file"] = "artifact_file"
    path: str
    reason: ArtifactFileFailureReason


class ArtifactVerificationDetails(PublicModel):
    kind: Literal["artifact_verification"] = "artifact_verification"
    path: str
    reason: str


class PartialPublicationDetails(PublicModel):
    kind: Literal["partial_publication"] = "partial_publication"
    destinations: list[ArtifactDestinationState]
    reason: str | None = None


ARTIFACT_PUBLICATION_FAILURE_SPECS = (
    FailureCodeSpec(
        "partial_publication",
        "The complete Artifact set was not published; no rollback was attempted",
        "execution",
        PartialPublicationDetails,
    ),
)
