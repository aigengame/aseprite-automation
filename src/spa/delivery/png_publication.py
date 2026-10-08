"""Staging, verification, and publication of one native-rendered PNG."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from spa.contracts.ports import (
    ArtifactFileObservation,
    ArtifactFiles,
    ArtifactVerificationEvidence,
    KernelInvocationResult,
    PngFacts,
    PngVerifier,
    RuntimeIssue,
)


class NativePngFacts(Protocol):
    """The common PNG observations within each caller's native facts model."""

    width: int
    height: int

    @property
    def color_profile(self) -> Literal["none", "srgb", "icc"]: ...

    alpha_min: int
    alpha_max: int
    rendered_byte_size: int


@dataclass
class StagedPng:
    """A scoped PNG and RGBA evidence pair, published only after verification."""

    png_file: Path
    rgba_file: Path
    _source: Path
    _destination: Path
    _if_exists: Literal["fail", "replace"]
    _files: ArtifactFiles
    _verify_png: PngVerifier
    _verified_sha256: str | None = field(default=None, init=False)

    def verify(
        self,
        native: NativePngFacts,
        invocation: KernelInvocationResult,
        *,
        matches_expected: bool,
        mismatch_message: str,
    ) -> PngFacts:
        """Check decoded bytes and the caller's own expected-facts verdict.

        Operation-specific postconditions and their failure meanings stay with the
        caller. In particular, this module does not classify invalid alpha bounds.
        """
        self._verified_sha256 = None
        staged_artifact = self._files.read_staged(self.png_file)
        decoded = self._verify_png(staged_artifact.payload, self.png_file)
        rendered_bytes = self._files.read_staged(self.rgba_file).payload
        if (
            not matches_expected
            or native.width != decoded.width
            or native.height != decoded.height
            or native.color_profile != decoded.color_profile
            or native.alpha_min != decoded.alpha_min
            or native.alpha_max != decoded.alpha_max
            or native.rendered_byte_size != native.width * native.height * 4
            or len(rendered_bytes) != native.rendered_byte_size
            or rendered_bytes != decoded.rgba_bytes
            or (native.alpha_min < 255 and not decoded.alpha_channel_present)
        ):
            raise RuntimeIssue(
                "artifact_verification_failed",
                mismatch_message,
                ArtifactVerificationEvidence(
                    str(self.png_file), "native and decoded facts differ"
                ),
                invocation.diagnostics,
            )
        self._verified_sha256 = staged_artifact.sha256
        return decoded

    def publish(self) -> ArtifactFileObservation:
        """Publish after verification and the caller's remaining domain checks."""
        if self._verified_sha256 is None:
            raise RuntimeError("PNG must pass verification before publication")
        self._files.ensure_source_separate(self._source, self._destination)
        return self._files.publish(
            self.png_file,
            self._destination,
            if_exists=self._if_exists,
            sha256=self._verified_sha256,
        )


@contextmanager
def staged_png(
    files: ArtifactFiles,
    verify_png: PngVerifier,
    *,
    source: Path,
    destination: str,
    if_exists: Literal["fail", "replace"],
) -> Iterator[StagedPng]:
    """Own both staged files across native execution, verification, and publish."""
    normalized = files.normalize_destination(destination)
    files.ensure_source_separate(source, normalized)
    png_file = files.staged_path(normalized, if_exists=if_exists)
    rgba_file = files.rendered_path(png_file)
    staged = StagedPng(
        png_file, rgba_file, source, normalized, if_exists, files, verify_png
    )
    try:
        yield staged
    finally:
        staged._verified_sha256 = None
        files.discard(png_file)
        files.discard(rgba_file)
