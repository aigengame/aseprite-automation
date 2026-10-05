"""The bounded image-then-metadata publication boundary for Sprite Sheets."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from spa.contracts.ports import (
    ArtifactFileObservation,
    ArtifactFiles,
    OperationIssue,
    RuntimeIssue,
)
from spa.delivery.sheet_contracts import (
    ExportSheetRequest,
    PartialPublication,
    PublicationState,
)


@dataclass(frozen=True)
class StagedSheet:
    image: Path
    metadata: Path
    pixels: Path
    image_destination: Path
    metadata_destination: Path
    _source: Path
    _request: ExportSheetRequest
    _files: ArtifactFiles

    def publish(
        self, image_sha: str, metadata_sha: str
    ) -> tuple[ArtifactFileObservation, ArtifactFileObservation]:
        files = self._files
        for destination in (self.image_destination, self.metadata_destination):
            files.ensure_source_separate(self._source, destination)
        image_existed = files.destination_exists(self.image_destination)
        metadata_existed = files.destination_exists(self.metadata_destination)
        image = files.publish(
            self.image,
            self.image_destination,
            if_exists=self._request.image_destination.if_exists,
            sha256=image_sha,
        )
        try:
            metadata = files.publish(
                self.metadata,
                self.metadata_destination,
                if_exists=self._request.metadata_destination.if_exists,
                sha256=metadata_sha,
            )
        except Exception as exc:
            # The local adapter reports failed atomic link/replace as not published.
            # An unexpected adapter failure cannot establish the destination state.
            known = isinstance(exc, RuntimeIssue) and exc.kind == "artifact_file_failed"
            raise OperationIssue(
                "partial_publication",
                "Image published; metadata publication failed. No rollback was attempted",
                PartialPublication(
                    destinations=(
                        PublicationState(
                            role="image",
                            path=str(self.image_destination),
                            existed_before_publication=image_existed,
                            state="published",
                            replaced_existing=image_existed,
                        ),
                        PublicationState(
                            role="metadata",
                            path=str(self.metadata_destination),
                            existed_before_publication=metadata_existed,
                            state="not_published" if known else "indeterminate",
                        ),
                    ),
                    reason=str(exc),
                ),
            ) from exc
        return image, metadata


@contextmanager
def staged_sheet(
    request: ExportSheetRequest, files: ArtifactFiles
) -> Iterator[StagedSheet]:
    source = Path(request.source_sprite_file)
    image = files.normalize_destination(request.image_destination.path)
    metadata = files.normalize_destination(request.metadata_destination.path)
    for destination in (image, metadata):
        files.ensure_source_separate(source, destination)
    files.ensure_source_separate(image, metadata)
    staged_image = files.staged_path(
        image, if_exists=request.image_destination.if_exists
    )
    staged_metadata = files.staged_path(
        metadata, if_exists=request.metadata_destination.if_exists
    )
    pixels = files.rendered_path(staged_image)
    try:
        yield StagedSheet(
            staged_image,
            staged_metadata,
            pixels,
            image,
            metadata,
            source,
            request,
            files,
        )
    finally:
        for path in (staged_image, staged_metadata, pixels):
            files.discard(path)
