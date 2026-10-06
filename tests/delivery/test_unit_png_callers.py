"""Behavioral baseline for both callers of staged PNG publication."""

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png import verify_png
from spa.adapters.png_input import decode_png_artifact
from spa.authoring.document.animation import AnimationPreviewRequest, preview_animation
from spa.contracts.digest import fnv1a64
from spa.contracts.ports import (
    ArtifactVerificationEvidence,
    HandlerEvidence,
    KernelInvocationResult,
    OperationServices,
    PngInputError,
    RuntimeIssue,
)
from spa.contracts.public import Diagnostics
from spa.delivery.export import ExportImageRequest, export_image
from tests.support import runtime_observation

RGBA = bytes((1, 2, 3, 128))
DIAGNOSTICS = Diagnostics(exit_status=0, stderr="native evidence")


@dataclass
class Caller:
    name: str
    source: Path
    original_source: Path
    destination: Path
    native: dict

    def run(self, services):
        fields = {
            "source_sprite_file": str(self.source),
            "destination": {"path": str(self.destination), "if_exists": "replace"},
        }
        if self.name == "export":
            return export_image(
                ExportImageRequest.model_validate(
                    {
                        **fields,
                        "frame_number": 1,
                        "export_image_area": {"kind": "canvas"},
                        "layer_composition": {"mode": "visible"},
                        "composition_color_mode": "preserve",
                        "color_mode": "preserve",
                        "color_profile": "preserve",
                        "transparency": "preserve",
                    }
                ),
                services,
            )
        return preview_animation(
            AnimationPreviewRequest.model_validate(
                {**fields, "earlier_frame": 1, "later_frame": 2}
            ),
            services,
        )


@pytest.fixture(params=("export", "preview"))
def caller(request, tmp_path):
    original = tmp_path / "original.aseprite"
    original.write_bytes(b"source bytes")
    source = tmp_path / "source.aseprite"
    source.symlink_to(original)
    destination = tmp_path / "image.png"
    destination.write_bytes(b"existing destination")
    native = {
        "width": 1,
        "height": 1,
        "color_mode": "rgb",
        "color_profile": "none",
        "alpha_min": 128,
        "alpha_max": 128,
        "rendered_byte_size": 4,
    }
    if request.param == "export":
        native.update(
            frame_number=1,
            source_color_mode="rgb",
            composition_color_mode="preserve",
            source_canvas={"width": 1, "height": 1},
            export_image_area={
                "kind": "canvas",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
            },
            resolved_layer_paths=[[1]],
            effective_background=False,
            stored_content_digest=fnv1a64(RGBA),
        )
    else:
        native.update(
            earlier_frame=1,
            later_frame=2,
            layer_order=["later", "earlier"],
            earlier_blend_mode="normal",
            earlier_opacity=128,
        )
    return Caller(request.param, source, original, destination, native)


class RecordingFiles(LocalArtifactFiles):
    def __init__(self):
        self.publications = []
        self.discarded = []

    def publish(self, staged, destination, *, if_exists, sha256):
        self.publications.append(destination)
        return super().publish(staged, destination, if_exists=if_exists, sha256=sha256)

    def discard(self, staged):
        self.discarded.append(staged)
        super().discard(staged)


def write_render(payload):
    png = Path(payload["staged_png_file"])
    rgba = Path(payload["staged_rgba_file"])
    Image.frombytes("RGBA", (1, 1), RGBA).save(png)
    rgba.write_bytes(RGBA)
    return png, rgba


def services(invoke, files, verifier=verify_png, decoder=decode_png_artifact):
    return OperationServices(
        probe_runtime=lambda _request: runtime_observation("aseprite_export_image"),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=files,
        verify_png=verifier,
        decode_png_artifact=decoder,
    )


@pytest.mark.parametrize(
    ("fault", "kind", "reason", "publication_attempts"),
    [
        ("native_rejected", "handler_rejected", "native refused", 0),
        ("malformed_response", "response_malformed", None, 0),
        ("missing_png", "artifact_file_failed", "staged_file_missing", 0),
        ("empty_png", "artifact_file_failed", "staged_file_empty", 0),
        ("malformed_png", "artifact_verification_failed", "PNG signature is absent", 0),
        ("missing_rgba", "artifact_file_failed", "staged_file_missing", 0),
        ("empty_rgba", "artifact_file_failed", "staged_file_empty", 0),
        (
            "short_rgba",
            "artifact_verification_failed",
            "native and decoded facts differ",
            0,
        ),
        (
            "different_rgba",
            "artifact_verification_failed",
            "native and decoded facts differ",
            0,
        ),
        (
            "wrong_width",
            "artifact_verification_failed",
            "native and decoded facts differ",
            0,
        ),
        (
            "wrong_profile",
            "artifact_verification_failed",
            "native and decoded facts differ",
            0,
        ),
        (
            "wrong_frame",
            "artifact_verification_failed",
            "native and decoded facts differ",
            0,
        ),
        (
            "wrong_byte_size",
            "artifact_verification_failed",
            "native and decoded facts differ",
            0,
        ),
        ("decoder_rejected", "artifact_verification_failed", "decoder refused", 0),
        ("source_alias_changed", "artifact_file_failed", "source_destination_alias", 0),
        ("png_changed", "artifact_file_failed", "staged_file_changed", 1),
        ("publication_failed", "artifact_file_failed", "publication_failed", 1),
    ],
)
def test_failure_preserves_destination_and_cleans_both_stages(
    caller, monkeypatch, fault, kind, reason, publication_attempts
):
    files = RecordingFiles()
    invocations = []

    def invoke(_observation, _handler, payload, _timeout):
        invocations.append(payload)
        png, rgba = write_render(payload)
        if fault == "native_rejected":
            raise RuntimeIssue(
                "handler_rejected",
                "Native refused",
                HandlerEvidence("/response.json", "native refused"),
                DIAGNOSTICS,
            )
        if fault == "malformed_response":
            caller.native.pop("width")
        elif fault == "missing_png":
            png.unlink()
        elif fault == "empty_png":
            png.write_bytes(b"")
        elif fault == "malformed_png":
            png.write_bytes(b"not a PNG")
        elif fault == "missing_rgba":
            rgba.unlink()
        elif fault == "empty_rgba":
            rgba.write_bytes(b"")
        elif fault == "short_rgba":
            rgba.write_bytes(RGBA[:-1])
        elif fault == "different_rgba":
            rgba.write_bytes(bytes((9, 2, 3, 128)))
        elif fault == "wrong_width":
            caller.native["width"] = 2
        elif fault == "wrong_profile":
            caller.native["color_profile"] = "srgb"
        elif fault == "wrong_frame":
            caller.native[
                "frame_number" if caller.name == "export" else "later_frame"
            ] = 3
        elif fault == "wrong_byte_size":
            caller.native["rendered_byte_size"] = 8
        elif fault == "source_alias_changed":
            caller.source.unlink()
            caller.source.symlink_to(caller.destination)
        return KernelInvocationResult(caller.native, "/response.json", DIAGNOSTICS)

    def verifier(payload, staged):
        if fault == "decoder_rejected":
            raise RuntimeIssue(
                "artifact_verification_failed",
                "Decoder refused",
                ArtifactVerificationEvidence(str(staged), "decoder refused"),
            )
        facts = verify_png(payload, staged)
        if fault == "png_changed":
            staged.write_bytes(payload + b"changed after verification")
        return facts

    def decoder(payload):
        if fault == "decoder_rejected":
            raise PngInputError("decoder refused")
        facts = decode_png_artifact(payload)
        if fault == "png_changed":
            Path(invocations[-1]["staged_png_file"]).write_bytes(
                payload + b"changed after verification"
            )
        return facts

    if fault == "publication_failed":

        def refuse_replace(*_args):
            raise PermissionError("publication denied")

        monkeypatch.setattr("spa.adapters.files.os.replace", refuse_replace)

    with pytest.raises(RuntimeIssue) as caught:
        caller.run(services(invoke, files, verifier, decoder))
    assert caught.value.kind == kind
    if reason is not None:
        if fault == "wrong_profile" and caller.name == "export":
            reason = "PNG representation differs from native export facts"
        assert caught.value.evidence.reason == reason
    assert len(invocations) == 1
    assert len(files.publications) == publication_attempts
    assert caller.destination.read_bytes() == b"existing destination"
    assert caller.original_source.read_bytes() == b"source bytes"
    assert {path.suffix for path in files.discarded} == {".png", ".rgba"}
    assert all(not path.exists() for path in files.discarded)


@pytest.mark.parametrize("also_mismatch", (False, True))
def test_alpha_bounds_classification_and_order_remain_operation_owned(
    caller, also_mismatch
):
    files = RecordingFiles()
    caller.native.update(alpha_min=200, alpha_max=100)

    def invoke(_observation, _handler, payload, _timeout):
        _, rgba = write_render(payload)
        if also_mismatch:
            rgba.write_bytes(bytes((9, 2, 3, 128)))
        return KernelInvocationResult(caller.native, "/response.json", DIAGNOSTICS)

    def verifier(payload, staged):
        # Preview retains its verifier port. Export uses the real artifact decoder,
        # whose alpha bounds are always computed from the independently decoded pixels.
        return replace(verify_png(payload, staged), alpha_min=200, alpha_max=100)

    with pytest.raises(RuntimeIssue) as caught:
        caller.run(services(invoke, files, verifier))
    assert caught.value.kind == "artifact_verification_failed"
    assert caught.value.evidence.reason == "native and decoded facts differ"
    assert caught.value.diagnostics == DIAGNOSTICS
    assert not files.publications
    assert caller.destination.read_bytes() == b"existing destination"
    assert all(not path.exists() for path in files.discarded)


def test_verified_callers_publish_once_and_report_actual_bytes(caller):
    files = RecordingFiles()
    invocations = []

    def invoke(_observation, _handler, payload, _timeout):
        invocations.append(payload)
        write_render(payload)
        return KernelInvocationResult(caller.native, "/response.json", DIAGNOSTICS)

    result = caller.run(services(invoke, files))
    actual = caller.destination.read_bytes()
    assert len(invocations) == 1
    assert files.publications == [caller.destination]
    assert result.artifact.byte_size == len(actual)
    assert result.artifact.sha256 == hashlib.sha256(actual).hexdigest()
    assert result.artifact.role == ("image" if caller.name == "export" else "preview")
    assert caller.original_source.read_bytes() == b"source bytes"
    assert len(files.discarded) == 2
    assert all(not path.exists() for path in files.discarded)
