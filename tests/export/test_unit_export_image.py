"""Export publication gates for controlled Kernel results."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png import verify_png
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationServices,
    RuntimeIssue,
)
from spa.contracts.public import Diagnostics
from spa.delivery.export import ExportImageRequest, export_image
from tests.support import runtime_observation


@pytest.mark.parametrize(
    ("native_output", "expected_kind"),
    [
        ("missing", "artifact_file_failed"),
        ("malformed", "artifact_verification_failed"),
        ("mismatch", "artifact_verification_failed"),
    ],
)
def test_export_does_not_publish_missing_malformed_or_mismatched_png(
    tmp_path: Path, native_output: str, expected_kind: str
) -> None:
    destination = tmp_path / "image.png"
    request = ExportImageRequest.model_validate(
        {
            "source_sprite_file": str(tmp_path / "source.aseprite"),
            "destination": {"path": str(destination), "if_exists": "fail"},
            "frame_number": 1,
            "color_mode": "preserve",
            "color_profile": "preserve",
            "transparency": "preserve",
        }
    )

    def invoke(_observation, _handler, payload, _timeout):
        staged = Path(payload["staged_png_file"])
        rendered = Path(payload["staged_rgba_file"])
        if native_output == "malformed":
            staged.write_bytes(b"not a PNG")
        elif native_output == "mismatch":
            output = BytesIO()
            Image.new("RGB", (1, 1), (1, 2, 3)).save(output, format="PNG")
            staged.write_bytes(output.getvalue())
            rendered.write_bytes(bytes((0, 0, 0, 255)))
        return KernelInvocationResult(
            payload={
                "frame_number": 1,
                "width": 1,
                "height": 1,
                "color_mode": "rgb",
                "color_profile": "none",
                "alpha_min": 255,
                "alpha_max": 255,
                "rendered_byte_size": 4,
            },
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    services = OperationServices(
        probe_runtime=lambda _request: runtime_observation("aseprite_export_image"),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
        verify_png=verify_png,
    )
    with pytest.raises(RuntimeIssue) as failure:
        export_image(request, services)

    assert failure.value.kind == expected_kind
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))
