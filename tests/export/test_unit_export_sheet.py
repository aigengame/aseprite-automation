"""Publication gates at the external Kernel and filesystem boundaries."""

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError as JsonSchemaError
from jsonschema import validate
from PIL import Image
from pydantic import ValidationError

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png_input import decode_png_input
from spa.contracts.ports import (
    ArtifactFileEvidence,
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    RuntimeIssue,
)
from spa.contracts.public import Diagnostics
from spa.delivery.sheet import export_sheet
from spa.delivery.sheet_contracts import ExportSheetRequest
from tests.support import runtime_observation


def request_for(folder: Path) -> ExportSheetRequest:
    return ExportSheetRequest.model_validate(
        {
            "source_sprite_file": str(folder / "source.aseprite"),
            "image_destination": {
                "path": str(folder / "sheet.png"),
                "if_exists": "fail",
            },
            "metadata_destination": {
                "path": str(folder / "sheet.json"),
                "if_exists": "fail",
            },
            "selection": {"kind": "range", "from_frame": 1, "to_frame": 2},
            "layer_composition": {"mode": "visible"},
            "output_color_mode": "rgb",
            "layout": {"kind": "horizontal"},
            "trim": "none",
            "padding": {"border": 0, "shape": 0, "inner": 0},
            "filename_format": "{frame1}",
        }
    )


@pytest.mark.parametrize(
    "field, value",
    [
        ("filename_format", "frame"),
        ("filename_format", "{frame1}-{frame0}"),
        ("filename_format", "{tag}_{frame1}"),
        ("filename_format", "{frame2}"),
        ("filename_format", "{frame1}\n"),
        ("output_color_mode", None),
        ("layout", {"kind": "rows", "columns": 0}),
        ("layout", {"kind": "packed", "power_of_two": True}),
        ("padding", {"border": 0, "shape": 101, "inner": 0}),
    ],
)
def test_request_and_discovery_schema_reject_unapproved_options(
    tmp_path: Path, field: str, value: object
) -> None:
    request = request_for(tmp_path).model_dump(mode="json")
    if value is None:
        del request[field]
    else:
        request[field] = value
    with pytest.raises(ValidationError):
        ExportSheetRequest.model_validate(request)
    with pytest.raises(JsonSchemaError):
        validate(request, ExportSheetRequest.model_json_schema())


def native_output(payload: dict, *, share_unequal: bool = False) -> dict:
    width = 1 if share_unequal else 2
    pixels = bytes((255, 0, 0, 255, 0, 0, 255, 255))
    image = Image.frombytes("RGBA", (width, 1), pixels[4:] if share_unequal else pixels)
    image.save(payload["staged_png_file"])
    Path(payload["staged_pixels_file"]).write_bytes(pixels)
    frames = [
        {
            "filename": str(n + 1),
            "frame": {"x": 0 if share_unequal else n, "y": 0, "w": 1, "h": 1},
            "sourceSize": {"w": 1, "h": 1},
            "spriteSourceSize": {"x": 0, "y": 0, "w": 1, "h": 1},
            "duration": 100,
            "rotated": False,
            "trimmed": False,
        }
        for n in range(2)
    ]
    Path(payload["staged_metadata_file"]).write_text(
        json.dumps(
            {
                "frames": frames,
                "meta": {
                    "image": "sheet.png",
                    "format": "RGBA8888",
                    "scale": "1",
                    "size": {"w": width, "h": 1},
                    "frameTags": [],
                },
            }
        )
    )
    return {
        "width": width,
        "height": 1,
        "source_width": 1,
        "source_height": 1,
        "color_mode": "rgb",
        "color_profile": "none",
        "source_frames": [1, 2],
        "frames": [
            {
                "frame_number": n + 1,
                "duration_ms": 100,
                "trim": {"x": 0, "y": 0, "width": 1, "height": 1},
                "pixels_offset": n * 4,
                "pixels_byte_size": 4,
            }
            for n in range(2)
        ],
        "source_tags": [],
        "effective_background": False,
        "layer_composition": {"mode": "visible"},
        "resolved_layer_paths": [[1]],
        "rendered_byte_size": 8,
    }


def services_for(invoke, files=None) -> OperationServices:
    return OperationServices(
        probe_runtime=lambda _: runtime_observation("aseprite_export_sheet"),
        invoke_kernel=lambda _runtime, _handler, payload, _timeout: (
            KernelInvocationResult(
                payload=invoke(payload),
                response_path="/response.json",
                diagnostics=Diagnostics(exit_status=0),
            )
        ),
        target_files=LocalTargetFiles(),
        artifact_files=files or LocalArtifactFiles(),
        decode_png_input=decode_png_input,
    )


def test_unequal_logical_frames_cannot_share_one_physical_rectangle(
    tmp_path: Path,
) -> None:
    services = services_for(lambda payload: native_output(payload, share_unequal=True))
    with pytest.raises(RuntimeIssue, match="files differ") as failure:
        export_sheet(request_for(tmp_path), services)
    assert failure.value.kind == "artifact_verification_failed"
    assert not (tmp_path / "sheet.png").exists()
    assert not (tmp_path / "sheet.json").exists()


def test_metadata_cannot_claim_success_for_the_wrong_layout(tmp_path: Path) -> None:
    request = request_for(tmp_path).model_dump()
    request["layout"] = {"kind": "vertical"}
    with pytest.raises(RuntimeIssue, match="files differ"):
        export_sheet(
            ExportSheetRequest.model_validate(request), services_for(native_output)
        )
    assert not (tmp_path / "sheet.png").exists()


@pytest.mark.parametrize(
    "damage",
    [
        "missing_image",
        "missing_metadata",
        "missing_pixels",
        "invalid_json",
        "invalid_png",
        "duration",
        "trimmed",
        "tag",
        "name",
        "profile",
        "source_size_type",
        "texture_size_type",
    ],
)
def test_any_unverified_counterpart_prevents_all_publication(
    tmp_path: Path, damage: str
) -> None:
    def invoke(payload):
        facts = native_output(payload)
        metadata = Path(payload["staged_metadata_file"])
        if damage.startswith("missing_"):
            Path(
                payload[
                    {
                        "missing_image": "staged_png_file",
                        "missing_metadata": "staged_metadata_file",
                        "missing_pixels": "staged_pixels_file",
                    }[damage]
                ]
            ).unlink()
        elif damage == "invalid_json":
            metadata.write_bytes(b"not json")
        elif damage == "invalid_png":
            Path(payload["staged_png_file"]).write_bytes(b"not png")
        elif damage == "profile":
            facts["color_profile"] = "srgb"
        else:
            value = json.loads(metadata.read_text())
            if damage == "duration":
                value["frames"][0]["duration"] = 101
            if damage == "trimmed":
                value["frames"][0]["trimmed"] = True
            if damage == "tag":
                value["meta"]["frameTags"] = [{"name": "made up"}]
            if damage == "name":
                value["frames"][0]["filename"] = "2"
            if damage == "source_size_type":
                value["frames"][0]["sourceSize"]["w"] = True
            if damage == "texture_size_type":
                value["meta"]["size"]["h"] = True
            metadata.write_text(json.dumps(value))
        return facts

    with pytest.raises(RuntimeIssue):
        export_sheet(request_for(tmp_path), services_for(invoke))
    assert (
        not (tmp_path / "sheet.png").exists() and not (tmp_path / "sheet.json").exists()
    )
    assert not list(tmp_path.glob(".*.staged.*"))


@pytest.mark.parametrize("rejection", [None, {}, {"message": 12, "reason": "bad"}])
def test_malformed_native_refusal_returns_a_response_failure(
    tmp_path: Path, rejection: object
) -> None:
    with pytest.raises(RuntimeIssue) as failure:
        export_sheet(
            request_for(tmp_path), services_for(lambda _: {"rejection": rejection})
        )
    assert failure.value.kind == "response_malformed"
    assert not (tmp_path / "sheet.png").exists()
    assert not (tmp_path / "sheet.json").exists()


def test_native_interruption_cleans_common_trim_auxiliary_files(tmp_path: Path) -> None:
    def interrupted(payload):
        # A killed native process cannot run its own finally/cleanup code.
        for path in (
            payload["staged_png_file"],
            payload["staged_metadata_file"],
            payload["staged_pixels_file"],
            payload["staged_trim_png_file"],
            payload["staged_trim_metadata_file"],
        ):
            Path(path).write_bytes(b"interrupted native output")
        raise TimeoutError("native process terminated")

    with pytest.raises(TimeoutError):
        export_sheet(request_for(tmp_path), services_for(interrupted))
    assert not list(tmp_path.iterdir())


def test_second_publication_failure_reports_both_paths_without_rollback(
    tmp_path: Path,
) -> None:
    (tmp_path / "sheet.png").write_bytes(b"old png")
    (tmp_path / "sheet.json").write_bytes(b"old metadata")

    class MetadataFailure(LocalArtifactFiles):
        def publish(self, staged, destination, *, if_exists, sha256):
            if destination.suffix == ".json":
                raise RuntimeIssue(
                    "artifact_file_failed",
                    "injected destination failure",
                    ArtifactFileEvidence(str(destination), "publication_failed"),
                )
            return super().publish(
                staged, destination, if_exists=if_exists, sha256=sha256
            )

    request = request_for(tmp_path)
    request.image_destination.if_exists = "replace"
    request.metadata_destination.if_exists = "replace"
    with pytest.raises(OperationIssue) as failure:
        export_sheet(request, services_for(native_output, MetadataFailure()))
    assert failure.value.code == "partial_publication"
    assert failure.value.details.model_dump()["destinations"] == [
        {
            "role": "image",
            "path": str(tmp_path / "sheet.png"),
            "existed_before": True,
            "state": "published",
            "replaced_existing": True,
        },
        {
            "role": "metadata",
            "path": str(tmp_path / "sheet.json"),
            "existed_before": True,
            "state": "not_published",
            "replaced_existing": None,
        },
    ]
    assert (tmp_path / "sheet.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "sheet.json").read_bytes() == b"old metadata"
    assert not list(tmp_path.glob(".*.staged.*"))


@pytest.mark.parametrize("destination", ["sheet.png", "sheet.json"])
def test_existing_fail_destination_is_rejected_before_runtime(
    tmp_path: Path, destination: str
) -> None:
    (tmp_path / destination).write_bytes(b"existing")

    def unexpected(*args):
        raise AssertionError("No native work is permitted before destination preflight")

    services = services_for(unexpected)
    from dataclasses import replace

    services = replace(services, probe_runtime=unexpected)
    with pytest.raises(RuntimeIssue) as failure:
        export_sheet(request_for(tmp_path), services)
    assert failure.value.evidence.reason == "destination_exists"
    assert (tmp_path / destination).read_bytes() == b"existing"
