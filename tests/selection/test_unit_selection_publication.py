"""Selection artifacts cannot publish on missing or contradictory evidence."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from spa.contracts import Diagnostics
from spa.file_adapter import LocalArtifactFiles, LocalTargetFiles
from spa.png_verifier import verify_png
from spa.ports import KernelInvocationResult, OperationServices, RuntimeIssue
from spa.selection import (
    SelectionExportRequest,
    SelectionPreviewRequest,
    export_selection,
    preview_selection,
)
from tests.support import runtime_observation


@pytest.mark.parametrize("operation", ["export", "preview"])
@pytest.mark.parametrize("defect", ["missing", "malformed", "mismatch"])
def test_artifact_verification_failure_preserves_existing_destination(
    tmp_path: Path, operation: str, defect: str
) -> None:
    preview = operation == "preview"
    target = tmp_path / ("mask.png" if preview else "mask.json")
    target.write_bytes(b"previous artifact")
    area = {"x": 10, "y": 20, "width": 1, "height": 1}
    request = {
        "coordinate_space": "canvas-pixel",
        "selection": {"kind": "all", "rectangle": area},
        "destination": {"path": str(target), "if_exists": "replace"},
    }

    def invoke(_observation, _handler, payload, _timeout):
        staged = Path(payload["staged_file"])
        if defect == "malformed":
            staged.write_bytes(b"invalid artifact")
        elif defect == "mismatch":
            if preview:
                output = BytesIO()
                Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(output, format="PNG")
                staged.write_bytes(output.getvalue())
                Path(payload["rendered_file"]).write_bytes(bytes([255] * 4))
            else:
                staged.write_text('{"kind":"empty"}')
        return KernelInvocationResult(
            payload={
                "coordinate_space": "canvas-pixel",
                "selection": {"kind": "all", "rectangle": area},
                "bounds": area,
                "pixel_count": 1,
            },
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    services = OperationServices(
        probe_runtime=lambda _request: runtime_observation("aseprite_selection"),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
        verify_png=verify_png,
    )
    with pytest.raises(RuntimeIssue) as failure:
        if preview:
            preview_selection(
                SelectionPreviewRequest.model_validate({**request, "canvas": area}),
                services,
            )
        else:
            export_selection(SelectionExportRequest.model_validate(request), services)
    assert failure.value.kind == (
        "artifact_file_failed"
        if defect == "missing"
        else "artifact_verification_failed"
    )
    assert target.read_bytes() == b"previous artifact"
    assert set(tmp_path.iterdir()) == {target}
