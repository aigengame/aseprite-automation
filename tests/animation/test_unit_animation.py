"""Animation Preview never publishes absent or unverified staged output."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from spa.animation import AnimationPreviewRequest, preview_animation
from spa.contracts import Diagnostics
from spa.file_adapter import LocalArtifactFiles, LocalTargetFiles
from spa.png_verifier import verify_png
from spa.ports import (
    KernelInvocationResult,
    OperationServices,
    RuntimeIssue,
    RuntimeObservation,
)


@pytest.mark.parametrize(
    ("native_output", "expected_kind"),
    [
        ("missing", "artifact_file_failed"),
        ("malformed", "artifact_verification_failed"),
        ("mismatch", "artifact_verification_failed"),
    ],
)
def test_preview_rejects_unverified_staging(
    tmp_path: Path, native_output: str, expected_kind: str
) -> None:
    destination = tmp_path / "preview.png"
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source is unchanged")
    request = AnimationPreviewRequest.model_validate(
        {
            "source_sprite_file": str(source),
            "earlier_frame": 1,
            "later_frame": 2,
            "destination": {"path": str(destination), "if_exists": "fail"},
        }
    )

    def invoke(_observation, _handler, payload, _timeout):
        staged = Path(payload["staged_png_file"])
        rendered = Path(payload["staged_rgba_file"])
        if native_output == "malformed":
            staged.write_bytes(b"not a PNG")
        elif native_output == "mismatch":
            output = BytesIO()
            Image.new("RGBA", (1, 1), (1, 2, 3, 255)).save(output, format="PNG")
            staged.write_bytes(output.getvalue())
            rendered.write_bytes(bytes((3, 2, 1, 255)))
        return KernelInvocationResult(
            payload={
                "earlier_frame": 1,
                "later_frame": 2,
                "width": 1,
                "height": 1,
                "color_mode": "rgb",
                "color_profile": "none",
                "alpha_min": 255,
                "alpha_max": 255,
                "rendered_byte_size": 4,
                "layer_order": ["later", "earlier"],
                "earlier_blend_mode": "normal",
                "earlier_opacity": 128,
            },
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    observation = RuntimeObservation(
        selection_source="explicit",
        requested_path="/aseprite",
        discovered_path="/aseprite",
        canonical_path="/aseprite",
        resource_path="/data/gui.xml",
        aseprite_version="test",
        api_version=41,
        lua_version="Lua 5.4",
        verified_prerequisites=("aseprite_scripting", "lua_file_io", "aseprite_json"),
        verified_capabilities=("aseprite_export_image",),
    )
    services = OperationServices(
        probe_runtime=lambda _request: observation,
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
        verify_png=verify_png,
    )
    with pytest.raises(RuntimeIssue) as failure:
        preview_animation(request, services)
    assert failure.value.kind == expected_kind
    assert not destination.exists()
    assert source.read_bytes() == b"source is unchanged"
    assert not list(tmp_path.glob("*.staged.png"))
    assert not list(tmp_path.glob("*.staged.rgba"))
