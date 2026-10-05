"""Shared Artifact publication and verification failure details."""

from typing import Literal

from spa.contracts.ports import ArtifactDestinationState, ArtifactFileFailureReason
from spa.contracts.public import PublicModel


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
