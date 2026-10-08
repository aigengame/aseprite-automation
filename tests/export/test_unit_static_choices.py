"""Static export gates bind independently decoded output to requested choices."""

from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from PIL import Image
from pydantic import ValidationError

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.palette_file import decode_palette_file
from spa.adapters.png_input import decode_png_artifact
from spa.application.surface import info_result
from spa.contracts.digest import fnv1a64
from spa.contracts.ports import KernelInvocationResult, OperationServices, RuntimeIssue
from spa.contracts.public import Diagnostics, RuntimeRequest
from spa.delivery.export import ExportImageRequest, export_image
from tests.support import runtime_observation


def request_fields(tmp_path):
    return {
        "source_sprite_file": str(tmp_path / "source.aseprite"),
        "destination": {"path": str(tmp_path / "result.png"), "if_exists": "replace"},
        "frame_number": 1,
        "export_image_area": {"kind": "canvas"},
        "layer_composition": {"mode": "visible"},
        "composition_color_mode": "preserve",
        "color_mode": "preserve",
        "color_profile": "preserve",
        "transparency": "preserve",
    }


@pytest.mark.parametrize("choice", ["assigned_profile", "opaque"])
def test_decoded_png_must_satisfy_explicit_choice_before_publication(
    tmp_path: Path, choice: str
):
    source, destination = tmp_path / "source.aseprite", tmp_path / "result.png"
    source.write_bytes(b"source unchanged")
    destination.write_bytes(b"destination unchanged")
    fields = request_fields(tmp_path)
    if choice == "assigned_profile":
        fields["color_profile"] = {"kind": "assign", "profile": {"kind": "srgb"}}
    else:
        fields["transparency"] = {
            "kind": "background",
            "background_color": {
                "kind": "rgba",
                "red": 0,
                "green": 0,
                "blue": 0,
                "alpha": 255,
            },
        }
    rgba = bytes((1, 2, 3, 128))

    def invoke(_runtime, _handler, payload, _timeout):
        Image.frombytes("RGBA", (1, 1), rgba).save(payload["staged_png_file"])
        Path(payload["staged_rgba_file"]).write_bytes(rgba)
        return KernelInvocationResult(
            {
                "frame_number": 1,
                "source_color_mode": "rgb",
                "composition_color_mode": "preserve",
                "source_canvas": {"width": 1, "height": 1},
                "export_image_area": {
                    "kind": "canvas",
                    "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                },
                "resolved_layer_paths": [[1]],
                "effective_background": choice == "opaque",
                "width": 1,
                "height": 1,
                "color_mode": "rgb",
                "color_profile": "none",
                "alpha_min": 128,
                "alpha_max": 128,
                "rendered_byte_size": 4,
                "stored_content_digest": fnv1a64(rgba),
            },
            "/response.json",
            Diagnostics(exit_status=0),
        )

    services = OperationServices(
        probe_runtime=lambda _request: runtime_observation(
            "aseprite_export_image",
            "aseprite_assign_color_profile",
            "aseprite_background_conversion",
        ),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
        decode_png_artifact=decode_png_artifact,
    )
    with pytest.raises(RuntimeIssue) as failure:
        export_image(ExportImageRequest.model_validate(fields), services)
    assert failure.value.kind == "artifact_verification_failed"
    assert source.read_bytes() == b"source unchanged"
    assert destination.read_bytes() == b"destination unchanged"
    assert not list(tmp_path.glob("*.staged.*"))


@pytest.mark.parametrize(
    "choice,capability",
    [
        ("assign", "aseprite_assign_color_profile"),
        ("convert", "aseprite_convert_color_profile"),
        ("color_mode", "aseprite_change_color_mode"),
        ("import", "aseprite_palette_files"),
        ("quantize", "aseprite_palette_quantization"),
        ("background", "aseprite_background_conversion"),
    ],
)
def test_unavailable_optional_behavior_is_discoverable_and_refused_before_kernel(
    tmp_path, choice, capability
):
    fields = request_fields(tmp_path)
    if choice in ("assign", "convert"):
        fields["color_profile"] = {"kind": choice, "profile": {"kind": "srgb"}}
    elif choice == "color_mode":
        fields["color_mode"] = {
            "source_color_mode": "grayscale",
            "target": {"color_mode": "rgb"},
        }
    elif choice == "background":
        fields["transparency"] = {
            "kind": "background",
            "background_color": {"kind": "grayscale", "gray": 0, "alpha": 255},
        }
    else:
        fields["color_mode"] = {
            "source_color_mode": "grayscale",
            "target": {
                "color_mode": "indexed",
                "rgb_map_algorithm": "default",
                "color_best_fit_criteria": "default",
            },
        }
        if choice == "import":
            palette = tmp_path / "colors.gpl"
            palette.write_text("GIMP Palette\n0 0 0 black\n255 255 255 white\n")
            fields["palette_preparation"] = {
                "kind": "import",
                "palette_file": {"format": "gpl", "path": str(palette)},
            }
        else:
            fields["palette_preparation"] = {
                "kind": "quantize",
                "max_colors": 2,
                "with_alpha": True,
                "rgb_map_algorithm": "octree",
                "new_layer_blending_method": True,
            }
    observed = runtime_observation(
        *(
            c
            for c in ("aseprite_export_image", "aseprite_change_color_mode")
            if c != capability
        )
    )
    source, destination = tmp_path / "source.aseprite", tmp_path / "result.png"
    source.write_bytes(b"source unchanged")
    destination.write_bytes(b"destination unchanged")

    def unexpected(*_args):
        pytest.fail("Unsupported optional operation reached the Kernel")

    services = OperationServices(
        probe_runtime=lambda _: observed,
        invoke_kernel=unexpected,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
        decode_png_artifact=decode_png_artifact,
        decode_palette_file=decode_palette_file,
    )
    with pytest.raises(RuntimeIssue) as failure:
        export_image(ExportImageRequest.model_validate(fields), services)
    assert failure.value.kind == "runtime_incompatible"
    assert failure.value.evidence.missing_capabilities == (capability,)
    assert destination.read_bytes() == b"destination unchanged"
    assert source.read_bytes() == b"source unchanged"
    assert not list(tmp_path.glob("*.staged.*"))
    info = info_result(RuntimeRequest(), services)
    assert "spa export image" in info.supported_capabilities
    assert any(
        gap.capability.startswith("spa export image:") and capability in gap.evidence
        for gap in info.capability_gaps
    )


@pytest.mark.parametrize("mapping,has_palette", [(True, False), (False, True)])
def test_schema_rejects_missing_or_inapplicable_palette(tmp_path, mapping, has_palette):
    fields = request_fields(tmp_path)
    if mapping:
        fields["color_mode"] = {
            "source_color_mode": "grayscale",
            "target": {
                "color_mode": "indexed",
                "rgb_map_algorithm": "default",
                "color_best_fit_criteria": "default",
            },
        }
    if has_palette:
        fields["palette_preparation"] = {"kind": "current"}
    with pytest.raises(ValidationError):
        ExportImageRequest.model_validate(fields)
    assert not Draft202012Validator(ExportImageRequest.model_json_schema()).is_valid(
        fields
    )
