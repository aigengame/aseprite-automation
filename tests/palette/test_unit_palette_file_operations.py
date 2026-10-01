"""Palette operation contracts and publication gates around native evidence."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.palette_file import decode_palette_file
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import info_result
from spa.authoring.color.palette_file import PaletteImportRequest, import_palette
from spa.authoring.color.quantization import (
    PaletteQuantizationRequest,
    quantize_palette,
)
from spa.contracts.ports import KernelInvocationResult, RuntimeIssue
from spa.contracts.public import Diagnostics, FailureEnvelope, RuntimeRequest
from spa.delivery.palette import (
    PALETTE_EXPORT_OPERATIONS,
    PaletteExportRequest,
    export_palette,
)
from tests.support import operation_services, runtime_observation


def _import_request() -> dict:
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": True,
        "palette_frame_number": 3,
        "palette_file": {"format": "gpl", "path": "colors.gpl"},
    }


def _quantization_request() -> dict:
    return {
        **{
            key: value
            for key, value in _import_request().items()
            if key != "palette_file"
        },
        "max_colors": 2,
        "with_alpha": True,
        "rgb_map_algorithm": "default",
        "new_layer_blending_method": False,
    }


def _export_request() -> dict:
    return {
        "source_sprite_file": "source.aseprite",
        "palette_source": {"kind": "effective", "frame_number": 3},
        "destination": {"format": "gpl", "path": "colors.gpl", "if_exists": "replace"},
    }


@pytest.mark.parametrize(
    ("model", "valid", "bad"),
    [
        (
            PaletteImportRequest,
            _import_request(),
            {"palette_file": {"format": "png", "path": "colors.gpl"}},
        ),
        (
            PaletteImportRequest,
            _import_request(),
            {
                "palette_file": {
                    "format": "gpl",
                    "path": "colors.gpl",
                    "scope": "sprite",
                }
            },
        ),
        (PaletteImportRequest, _import_request(), {"palette_frame_number": None}),
        (PaletteQuantizationRequest, _quantization_request(), {"with_alpha": None}),
        (
            PaletteQuantizationRequest,
            _quantization_request(),
            {"rgb_map_algorithm": "nearest"},
        ),
        (PaletteQuantizationRequest, _quantization_request(), {"max_colors": 257}),
        (PaletteQuantizationRequest, _quantization_request(), {"use_range": False}),
        (
            PaletteExportRequest,
            _export_request(),
            {"palette_source": {"kind": "effective"}},
        ),
        (
            PaletteExportRequest,
            _export_request(),
            {
                "palette_source": {
                    "kind": "effective",
                    "frame_number": 3,
                    "layer": "all",
                }
            },
        ),
        (
            PaletteExportRequest,
            _export_request(),
            {
                "destination": {
                    "format": "png",
                    "path": "colors.gpl",
                    "if_exists": "replace",
                }
            },
        ),
        (
            PaletteExportRequest,
            _export_request(),
            {"destination": {"format": "gpl", "path": "colors.gpl"}},
        ),
    ],
)
def test_request_validation_matches_published_json_schema(model, valid, bad) -> None:
    validator = Draft202012Validator(model.model_json_schema())
    assert validator.is_valid(valid)
    model.model_validate(valid)
    invalid = valid | bad
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        model.model_validate(invalid)


def test_quantization_requires_every_explicit_option_in_model_and_schema() -> None:
    valid = _quantization_request()
    validator = Draft202012Validator(PaletteQuantizationRequest.model_json_schema())
    for option in (
        "max_colors",
        "with_alpha",
        "rgb_map_algorithm",
        "new_layer_blending_method",
    ):
        missing = valid.copy()
        missing.pop(option)
        assert not validator.is_valid(missing)
        with pytest.raises(ValidationError):
            PaletteQuantizationRequest.model_validate(missing)


def _change(frame: int, end: int, rgba: tuple[int, int, int, int]) -> dict:
    return {
        "palette_frame_number": frame,
        "effective_frame_range": {"from_frame": frame, "to_frame": end},
        "entries": [
            {"index": 0, "color": dict(zip(("red", "green", "blue", "alpha"), rgba))}
        ],
    }


def _timeline() -> dict:
    first = _change(1, 2, (1, 2, 3, 255))
    second = _change(3, 4, (4, 5, 6, 128))
    return {"frame_count": 4, "palette_changes": [first, second], "palette": second}


def _files(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    destination = tmp_path / "colors.gpl"
    source.write_bytes(b"original source")
    target.write_bytes(b"original target")
    destination.write_bytes(b"original destination")
    return source, target, destination


def _services(invoke, *, artifact_files=None, decode=decode_palette_file):
    return replace(
        operation_services(lambda _: runtime_observation("aseprite_palette_files")),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=artifact_files or LocalArtifactFiles(),
        decode_palette_file=decode,
    )


@pytest.mark.parametrize("fault", ["wrong_change", "native_loss", "not_reopened"])
def test_import_refuses_unverified_native_palette_without_target_commit(
    tmp_path: Path, fault: str
) -> None:
    source, target, palette_file = _files(tmp_path)
    palette_file.write_bytes(b"GIMP Palette\nChannels: RGBA\n4 5 6 128 named\n")
    evidence = _timeline() | {"persisted_reopen_verified": True}
    if fault == "wrong_change":
        evidence["palette"] = evidence["palette_changes"][0]
    elif fault == "native_loss":
        evidence["palette_changes"][1] = _change(3, 4, (4, 5, 7, 255))
        evidence["palette"] = evidence["palette_changes"][1]
    else:
        evidence["persisted_reopen_verified"] = False

    def invoke(_runtime, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"unverified output")
        return KernelInvocationResult(
            evidence, "/response.json", Diagnostics(exit_status=0)
        )

    request = PaletteImportRequest.model_validate(
        _import_request()
        | {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "palette_file": {"format": "gpl", "path": str(palette_file)},
        }
    )
    expected_kind = (
        "artifact_verification_failed"
        if fault == "native_loss"
        else "response_malformed"
    )
    with pytest.raises(RuntimeIssue) as caught:
        import_palette(request, _services(invoke))
    assert caught.value.kind == expected_kind
    assert source.read_bytes() == b"original source"
    assert target.read_bytes() == b"original target"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "colors.gpl",
        "source.aseprite",
        "target.aseprite",
    ]


@pytest.mark.parametrize("fault", ["wrong_frame", "wrong_options", "not_reopened"])
def test_quantization_refuses_false_native_evidence_without_target_commit(
    tmp_path: Path, fault: str
) -> None:
    source, target, _ = _files(tmp_path)
    evidence = _timeline() | {
        "persisted_reopen_verified": True,
        "quantization": {
            "rendered_frames": [1, 2, 3, 4],
            "affected_frames": [3, 4],
            "requested_max_colors": 2,
            "actual_colors": 1,
            "with_alpha": True,
            "rgb_map_algorithm": "default",
            "effective_rgb_map_algorithm": "octree",
            "new_layer_blending_method": False,
        },
    }
    if fault == "wrong_frame":
        evidence["palette"] = evidence["palette_changes"][0]
    elif fault == "wrong_options":
        evidence["quantization"]["with_alpha"] = False
    else:
        evidence["persisted_reopen_verified"] = False

    def invoke(_runtime, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"unverified output")
        return KernelInvocationResult(
            evidence, "/response.json", Diagnostics(exit_status=0)
        )

    request = PaletteQuantizationRequest.model_validate(
        _quantization_request()
        | {"source_sprite_file": str(source), "target_sprite_file": str(target)}
    )
    with pytest.raises(RuntimeIssue) as caught:
        quantize_palette(request, _services(invoke))
    assert caught.value.kind == "response_malformed"
    assert source.read_bytes() == b"original source"
    assert target.read_bytes() == b"original target"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "colors.gpl",
        "source.aseprite",
        "target.aseprite",
    ]


class _RecordingFiles(LocalArtifactFiles):
    def __init__(self) -> None:
        self.published: list[Path] = []
        self.discarded: list[Path] = []

    def publish(self, staged, destination, *, if_exists, sha256):
        self.published.append(destination)
        return super().publish(staged, destination, if_exists=if_exists, sha256=sha256)

    def discard(self, staged):
        self.discarded.append(staged)
        super().discard(staged)


@pytest.mark.parametrize(
    "fault", ["wrong_frame", "native_loss", "invalid_file", "digest_changed"]
)
def test_export_refuses_unverified_file_without_replacing_destination(
    tmp_path: Path, fault: str
) -> None:
    source, target, destination = _files(tmp_path)
    files = _RecordingFiles()
    evidence = _timeline()
    raw = b"GIMP Palette\nChannels: RGBA\n4 5 6 128 named\n"
    staged_path = None

    def invoke(_runtime, _handler, payload, _timeout):
        nonlocal staged_path
        staged = Path(payload["staged_palette_file"])
        staged_path = staged
        staged.write_bytes(raw if fault != "invalid_file" else b"bad file")
        if fault == "wrong_frame":
            evidence["palette"] = evidence["palette_changes"][0]
        elif fault == "native_loss":
            evidence["palette_changes"][1] = _change(3, 4, (7, 8, 9, 255))
            evidence["palette"] = evidence["palette_changes"][1]
        return KernelInvocationResult(
            evidence, "/response.json", Diagnostics(exit_status=0)
        )

    def decode(payload, file_format):
        facts = decode_palette_file(payload, file_format)
        if fault == "digest_changed":
            assert staged_path is not None
            staged_path.write_bytes(payload + b"changed after verification")
        return facts

    request = PaletteExportRequest.model_validate(
        _export_request()
        | {
            "source_sprite_file": str(source),
            "destination": {
                "format": "gpl",
                "path": str(destination),
                "if_exists": "replace",
            },
        }
    )
    with pytest.raises(RuntimeIssue) as caught:
        export_palette(request, _services(invoke, artifact_files=files, decode=decode))
    assert caught.value.kind == {
        "wrong_frame": "response_malformed",
        "digest_changed": "artifact_file_failed",
    }.get(fault, "artifact_verification_failed")
    assert files.published == ([destination] if fault == "digest_changed" else [])
    assert len(files.discarded) == 1 and not files.discarded[0].exists()
    assert source.read_bytes() == b"original source"
    assert target.read_bytes() == b"original target"
    assert destination.read_bytes() == b"original destination"


@pytest.mark.parametrize("generate", [False, True])
def test_effective_export_does_not_require_native_quantization(tmp_path, generate):
    source, _, destination = _files(tmp_path)
    raw = b"GIMP Palette\nChannels: RGBA\n4 5 6 128 named\n"
    calls = []

    def invoke(_runtime, _handler, payload, _timeout):
        calls.append(payload)
        Path(payload["staged_palette_file"]).write_bytes(raw)
        return KernelInvocationResult(
            _timeline(), "/response.json", Diagnostics(exit_status=0)
        )

    services = replace(
        _services(invoke),
        probe_runtime=lambda _: runtime_observation(
            "aseprite_sprite_inspection", "aseprite_palette_files"
        ),
    )
    request = _export_request() | {
        "source_sprite_file": str(source),
        "destination": {
            "format": "gpl",
            "path": str(destination),
            "if_exists": "replace",
        },
    }
    if generate:
        request["palette_source"] = {
            "kind": "color-quantization",
            **{
                key: value
                for key, value in _quantization_request().items()
                if key
                in {
                    "palette_frame_number",
                    "max_colors",
                    "with_alpha",
                    "rgb_map_algorithm",
                    "new_layer_blending_method",
                }
            },
        }
    result = dispatch(
        PALETTE_EXPORT_OPERATIONS[0], json.dumps(request), {}, services, FAILURE_CODES
    )
    if generate:
        assert isinstance(result, FailureEnvelope)
        assert result.code == "runtime_incompatible"
        assert result.details.model_dump()["missing_capabilities"] == [
            "aseprite_palette_quantization"
        ]
        assert calls == [] and destination.read_bytes() == b"original destination"
    else:
        assert result.status == "success", result
        assert len(calls) == 1 and destination.read_bytes() == raw
    assert source.read_bytes() == b"original source"
    info = info_result(RuntimeRequest(), services)
    assert "spa palette export" in info.supported_capabilities
    assert "spa palette color-quantization" not in info.supported_capabilities
    assert any(
        gap.capability == "spa palette export: color-quantization"
        for gap in info.capability_gaps
    )
