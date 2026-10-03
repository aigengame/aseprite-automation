"""Preparation dispatch checks independent PNG bytes before publishing an Artifact.

The native boundary replays declared observations and literal pixels; these fast
checks do not claim to exercise Aseprite's transformations or color algorithms.
"""

import hashlib
import json
import struct
import zlib
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from PIL import Image, ImageCms, PngImagePlugin

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png_input import decode_png_input
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.contracts.digest import fnv1a64
from spa.contracts.ports import KernelInvocationResult, OperationServices
from spa.contracts.public import Diagnostics
from spa.preparation.raster import PREPARATION_OPERATIONS
from tests.preparation.support import specification
from tests.support import runtime_observation

DESCRIPTOR = PREPARATION_OPERATIONS[0]
SOURCE_PIXELS = [
    (180, 70, 30, 255),
    (30, 90, 180, 255),
    (44, 11, 66, 0),
    (180, 70, 30, 127),
    (30, 90, 180, 128),
    (0, 0, 0, 0),
]
PREPARED_PIXELS = [(0, 0, 0, 0)] * 20
PREPARED_PIXELS[6] = (180, 70, 30, 255)
PREPARED_PIXELS[7] = (30, 90, 180, 255)
PREPARED_PIXELS[12] = (30, 90, 180, 255)


def _png(path, pixels=SOURCE_PIXELS, *, mode="RGBA", metadata=None, icc=None):
    image = Image.new(mode, (3, 2))
    if mode == "RGBA":
        image.putdata(pixels)
    options = {}
    if metadata is not None:
        options["pnginfo"] = metadata
    if icc is not None:
        options["icc_profile"] = icc
    image.save(path, **options)


def _replace_chunk(path, kind, data):
    """Replace one encoded fixture chunk, preserving its CRC and other bytes."""
    payload = path.read_bytes()
    output, offset = bytearray(payload[:8]), 8
    while offset < len(payload):
        size = struct.unpack_from(">I", payload, offset)[0]
        chunk_kind = payload[offset + 4 : offset + 8]
        if chunk_kind == kind:
            if data is not None:
                output.extend(struct.pack(">I", len(data)) + kind + data)
                output.extend(struct.pack(">I", zlib.crc32(kind + data)))
        else:
            output.extend(payload[offset : offset + 12 + size])
        offset += 12 + size
    path.write_bytes(output)


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


class NativeReplay:
    """Synthetic external response plus independently constructed staged bytes."""

    def __init__(self):
        self.calls = []
        self.pixels = PREPARED_PIXELS
        self.fault = None

    def __call__(self, _runtime, _handler, payload, _timeout):
        self.calls.append(payload)
        spec = payload["specification"]
        geometry = payload["geometry"]
        rgba = bytes(channel for pixel in self.pixels for channel in pixel)
        entries = spec["palette"]["entries"]
        colors = [
            tuple(c[key] for key in ("red", "green", "blue", "alpha")) for c in entries
        ]
        metadata = PngImagePlugin.PngInfo()
        metadata.add(b"sRGB", b"\x00")
        png_path = Path(payload["staged_png_file"])
        rgba_path = Path(payload["staged_rgba_file"])
        if spec["output_mode"] == "indexed":
            stored = bytes(colors.index(pixel) for pixel in self.pixels)
            image = Image.frombytes("P", (5, 4), stored)
            image.putpalette([channel for color in colors for channel in color[:3]])
            image.save(
                png_path,
                pnginfo=metadata,
                transparency=bytes(c[3] for c in colors),
                bits=8,
            )
            # Pillow pads 8-bit PLTE to 256 entries; this fixture preserves the
            # caller's complete shorter Palette as the native encoder must.
            _replace_chunk(
                png_path,
                b"PLTE",
                bytes(channel for color in colors for channel in color[:3]),
            )
        else:
            stored = rgba
            Image.frombytes("RGBA", (5, 4), rgba).save(png_path, pnginfo=metadata)
        rgba_path.write_bytes(rgba)
        facts = {
            "width": 5,
            "height": 4,
            "color_profile": "srgb",
            "alpha_min": min(pixel[3] for pixel in self.pixels),
            "alpha_max": max(pixel[3] for pixel in self.pixels),
            "rendered_byte_size": 80,
            "source_rgba_digest": fnv1a64(
                bytes.fromhex(payload["decoded"]["rgba_bytes"])
            ),
            "normalized_rgba_digest": fnv1a64(
                bytes.fromhex(payload["decoded"]["rgba_bytes"])
            ),
            "normalized_alpha_preserved": True,
            "profile": {
                "source_kind": "none",
                "source_icc_identity": None,
                "assumption": "srgb",
                "effective": "srgb",
                "converted": False,
            },
            "crop": geometry["crop"],
            "resized": geometry["resized"],
            "offset": geometry["offset"],
            "mapping": {
                "requested_rgb_map_algorithm": "octree",
                "effective_rgb_map_algorithm": "octree",
                "color_best_fit_criteria": "rgb",
            },
            "dithering": {
                "requested_algorithm": "none",
                "effective_algorithm": "none",
                "matrix": None,
                "dithering_factor": None,
                "effective_factor_percent": None,
            },
            "palette_entries": deepcopy(entries),
            "transparent_index": spec["palette"]["transparent_index"],
            "output_mode": spec["output_mode"],
            "stored_content_digest": fnv1a64(stored),
            "rgba_content_digest": fnv1a64(rgba),
        }
        if self.fault is not None:
            self.fault(facts, png_path, rgba_path)
        return KernelInvocationResult(facts, "/native-response.json", Diagnostics())


@pytest.fixture
def preparation(tmp_path):
    source, destination = tmp_path / "input.png", tmp_path / "prepared.png"
    _png(source)
    request = {
        "raster_file": str(source),
        "intent": {"kind": "initial"},
        "specification": specification(),
        "destination": {"path": str(destination), "if_exists": "replace"},
    }
    files, native = RecordingFiles(), NativeReplay()
    runtime = runtime_observation(
        *DESCRIPTOR.runtime_requirements.required_capabilities
    )
    services = OperationServices(
        probe_runtime=lambda _: runtime,
        invoke_kernel=native,
        target_files=LocalTargetFiles(),
        artifact_files=files,
        decode_png_input=decode_png_input,
    )
    return request, services, native, files, source, destination


def _call(request, services):
    result = dispatch(
        DESCRIPTOR, json.dumps(request), {}, services, FAILURE_CODES
    ).model_dump(mode="json")
    schema = DESCRIPTOR.schema(FAILURE_CODES)
    Draft202012Validator(
        schema.result_schema if result["status"] == "success" else schema.failure_schema
    ).validate(result)
    return result


def _clean(files):
    assert all(not stage.exists() for stage in files.discarded)


@pytest.mark.parametrize("mode", ("rgba", "indexed"))
def test_initial_and_reproduction_publish_verified_literal_pixels(preparation, mode):
    request, services, native, files, source, destination = preparation
    request["specification"]["output_mode"] = mode
    original = source.read_bytes()
    result = _call(request, services)
    assert result["status"] == "success", result
    record = result["reproduction"]
    assert record["source_identity"] == {
        "byte_size": len(original),
        "sha256": hashlib.sha256(original).hexdigest(),
    }
    assert record["geometry"]["offset"] == {"x": 1, "y": 1}
    assert record["geometry"]["anchors"] == [{"name": "foot", "x": 2, "y": 3}]
    assert record["profile"]["assumption"] == "srgb"
    with Image.open(destination) as image:
        assert list(image.convert("RGBA").get_flattened_data()) == PREPARED_PIXELS
        assert image.info["srgb"] == 0
        assert "icc_profile" not in image.info
        assert image.mode == ("P" if mode == "indexed" else "RGBA")
    assert (
        result["artifact"]["sha256"]
        == hashlib.sha256(destination.read_bytes()).hexdigest()
    )
    request["intent"] = {"kind": "reproduce", "expected": record}
    repeated = _call(request, services)
    assert repeated["reproduction"] == record
    assert bytes.fromhex(native.calls[0]["raster_bytes"]) == original
    assert source.read_bytes() == original
    assert files.publications == [destination, destination]
    _clean(files)


@pytest.mark.parametrize(
    "change",
    [
        "omitted_intent",
        "incomplete_reproduction",
        "transparent_hidden_rgb",
        "missing_transparency",
        "multiple_transparency",
        "transparent_index_outside_palette",
        "transparent_index_negative",
        "transparent_index_256",
        "one_palette_entry",
        "257_palette_entries",
        "256_opaque_entries",
    ],
)
def test_invalid_intent_and_palette_are_rejected_before_native(preparation, change):
    request, services, native, files, source, destination = preparation
    palette = request["specification"]["palette"]
    if change == "omitted_intent":
        request.pop("intent")
    elif change == "incomplete_reproduction":
        request["intent"] = {"kind": "reproduce"}
    elif change == "transparent_hidden_rgb":
        palette["entries"][0]["red"] = 1
    elif change == "missing_transparency":
        palette["entries"][0]["alpha"] = 255
    elif change == "multiple_transparency":
        palette["entries"][1]["alpha"] = 0
    elif change == "transparent_index_outside_palette":
        palette["transparent_index"] = 7
    elif change == "transparent_index_negative":
        palette["transparent_index"] = -1
    elif change == "transparent_index_256":
        palette["transparent_index"] = 256
    elif change == "one_palette_entry":
        palette["entries"] = palette["entries"][:1]
    elif change == "257_palette_entries":
        palette["entries"] += [palette["entries"][1]] * 254
    else:
        palette["entries"] = [palette["entries"][1]] * 256
    destination.write_bytes(b"retained destination")
    original = source.read_bytes()
    result = _call(request, services)
    assert result["code"] == "invalid_request"
    assert not native.calls and not files.publications
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"retained destination"
    assert not files.discarded


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("malformed", "input"),
        ("indexed", "input"),
        ("grayscale", "input"),
        ("invalid_icc", "input"),
        ("unsupported_icc", "color_profile"),
        ("conflicting_metadata", "input"),
        ("untagged_with_gamma", "input"),
        ("invalid_srgb_intent", "input"),
    ],
)
def test_unsupported_encoded_input_preserves_originals(preparation, kind, reason):
    request, services, native, files, source, destination = preparation
    if kind == "malformed":
        source.write_bytes(b"not PNG")
    elif kind == "indexed":
        image = Image.new("P", (3, 2))
        image.putpalette([0, 0, 0, 255, 255, 255])
        image.save(source, bits=8)
    elif kind == "grayscale":
        _png(source, mode="L")
    elif kind == "invalid_icc":
        _png(source, icc=b"invalid ICC data")
    elif kind == "unsupported_icc":
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        _png(source, icc=profile)
    else:
        metadata = PngImagePlugin.PngInfo()
        if kind == "conflicting_metadata":
            metadata.add(b"sRGB", b"\x00")
            metadata.add(b"gAMA", struct.pack(">I", 100000))
        elif kind == "untagged_with_gamma":
            metadata.add(b"gAMA", struct.pack(">I", 45455))
        else:
            metadata.add(b"sRGB", b"\x04")
        _png(source, metadata=metadata)
    original = source.read_bytes()
    destination.write_bytes(b"retained destination")
    result = _call(request, services)
    assert result["code"] == "preparation_rejected"
    assert result["details"]["reason"] == reason
    assert not native.calls and not files.publications
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"retained destination"
    assert not files.discarded


@pytest.mark.parametrize("transparent_index", (0, 7, 255))
def test_indexed_output_retains_declared_palette_and_transparent_index(
    preparation, transparent_index
):
    request, services, _native, _files, _source, destination = preparation
    spec = request["specification"]
    spec["output_mode"] = "indexed"
    opaque = spec["palette"]["entries"][1:]
    entries = [deepcopy(opaque[0]), deepcopy(opaque[1])]
    # Unused duplicates are retained; native tie selection is exercised by e2e.
    entries += [deepcopy(opaque[0])] * (max(3, transparent_index + 1) - 3)
    entries.insert(transparent_index, {"red": 0, "green": 0, "blue": 0, "alpha": 0})
    spec["palette"] = {"entries": entries, "transparent_index": transparent_index}
    result = _call(request, services)
    assert result["status"] == "success", result
    assert result["reproduction"]["content"]["palette"] == spec["palette"]
    expected_indices = [transparent_index] * 20
    expected_indices[6] = 1 if transparent_index == 0 else 0
    expected_indices[7] = expected_indices[12] = 2 if transparent_index == 0 else 1
    with Image.open(destination) as image:
        assert list(image.get_flattened_data()) == expected_indices
        assert len(image.getpalette()) == len(entries) * 3
        assert image.info["transparency"] == transparent_index
        assert list(image.convert("RGBA").get_flattened_data()) == PREPARED_PIXELS


@pytest.mark.parametrize(
    ("change", "reason", "additional_native_calls"),
    [
        ("changed_input", "changed_input", 0),
        ("specification", "reproduction", 0),
        ("runtime", "reproduction", 0),
        ("retained_pixels", "reproduction", 1),
        ("retained_stored_indices", "reproduction", 1),
        ("retained_mapping", "reproduction", 1),
    ],
)
def test_reproduction_mismatch_never_publishes(
    preparation, change, reason, additional_native_calls
):
    request, services, native, files, source, destination = preparation
    if change == "retained_stored_indices":
        request["specification"]["output_mode"] = "indexed"
    initial = _call(request, services)
    assert initial["status"] == "success", initial
    published = destination.read_bytes()
    request["intent"] = {"kind": "reproduce", "expected": initial["reproduction"]}
    if change == "changed_input":
        _png(source, pixels=[(255, 255, 255, 255)] * 6)
    elif change == "specification":
        request["specification"]["alpha_threshold"] = 127
    elif change == "runtime":
        observed = runtime_observation(
            *DESCRIPTOR.runtime_requirements.required_capabilities
        )
        services = replace(
            services,
            probe_runtime=lambda _: replace(observed, aseprite_version="another"),
        )
    elif change == "retained_stored_indices":
        request["intent"]["expected"]["content"]["stored_sha256"] = "a" * 64
    elif change == "retained_pixels":
        request["intent"]["expected"]["content"]["rgba_sha256"] = "a" * 64
    else:
        request["intent"]["expected"]["mapping"]["effective_rgb_map_algorithm"] = (
            "rgb5a3"
        )
    original = source.read_bytes()
    result = _call(request, services)
    assert result["code"] == "preparation_rejected"
    assert result["details"]["reason"] == reason
    assert len(native.calls) == 1 + additional_native_calls
    assert files.publications == [destination]
    assert source.read_bytes() == original
    assert destination.read_bytes() == published
    _clean(files)


def test_reproduction_missing_input_does_not_publish(preparation):
    request, services, native, files, source, destination = preparation
    result = _call(request, services)
    assert result["status"] == "success", result
    request["intent"] = {"kind": "reproduce", "expected": result["reproduction"]}
    previous = destination.read_bytes()
    source.unlink()
    failure = _call(request, services)
    assert failure["code"] == "artifact_file_failed"
    assert failure["details"]["reason"] == "input_file_unreadable"
    assert destination.read_bytes() == previous
    assert len(native.calls) == 1 and files.publications == [destination]


@pytest.mark.parametrize(
    ("fault", "code"),
    [
        ("mapping_rejected", "preparation_rejected"),
        ("malformed_native", "kernel_response_invalid"),
        ("source_digest", "artifact_verification_failed"),
        ("normalized_digest", "artifact_verification_failed"),
        ("native_geometry", "artifact_verification_failed"),
        ("native_profile", "artifact_verification_failed"),
        ("native_palette", "artifact_verification_failed"),
        ("native_mapping", "artifact_verification_failed"),
        ("native_dithering", "artifact_verification_failed"),
        ("native_alpha", "artifact_verification_failed"),
        ("missing_profile", "artifact_verification_failed"),
        ("retained_icc", "artifact_verification_failed"),
        ("wrong_rendering_intent", "artifact_verification_failed"),
        ("rgba_rgb_format", "artifact_verification_failed"),
        ("palette_color", "artifact_verification_failed"),
        ("transparent_hidden_rgb", "artifact_verification_failed"),
        ("indexed_palette", "artifact_verification_failed"),
        ("last_pixel", "artifact_verification_failed"),
        ("rgba_sidecar", "artifact_verification_failed"),
    ],
)
def test_contradictory_native_or_encoded_facts_never_publish(preparation, fault, code):
    request, services, native, files, source, destination = preparation
    if fault == "indexed_palette":
        request["specification"]["output_mode"] = "indexed"
    destination.write_bytes(b"retained destination")
    original = source.read_bytes()

    def tamper(facts, png_path, rgba_path):
        if fault == "mapping_rejected":
            facts.clear()
            facts["rejection"] = {
                "code": "preparation_rejected",
                "details": {
                    "kind": "preparation",
                    "reason": "mapping",
                    "message": "Native mapping refused",
                },
            }
        elif fault == "malformed_native":
            facts.pop("width")
        elif fault in ("source_digest", "normalized_digest"):
            facts[
                "source_rgba_digest"
                if fault == "source_digest"
                else "normalized_rgba_digest"
            ] = "0" * 16
        elif fault == "native_geometry":
            facts["offset"]["x"] = 2
        elif fault == "native_profile":
            facts["profile"]["assumption"] = None
        elif fault == "native_palette":
            facts["palette_entries"][1]["red"] = 181
        elif fault == "native_mapping":
            facts["mapping"]["effective_rgb_map_algorithm"] = "rgb5a3"
        elif fault == "native_dithering":
            facts["dithering"]["effective_algorithm"] = "ordered"
        elif fault == "native_alpha":
            facts["alpha_min"] = 255
        elif fault == "missing_profile":
            _replace_chunk(png_path, b"sRGB", None)
        elif fault == "retained_icc":
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            with Image.open(png_path) as image:
                image.save(png_path, icc_profile=profile)
        elif fault == "wrong_rendering_intent":
            _replace_chunk(png_path, b"sRGB", b"\x03")
        elif fault == "rgba_rgb_format":
            metadata = PngImagePlugin.PngInfo()
            metadata.add(b"sRGB", b"\x00")
            with Image.open(png_path) as image:
                image.convert("RGB").save(png_path, pnginfo=metadata)
        elif fault == "indexed_palette":
            # Keep native digest and sidecar consistent with these wrong Palette
            # bytes, so independently checking the requested Palette must reject.
            _replace_chunk(
                png_path, b"PLTE", bytes((0, 0, 0, 181, 70, 30, 30, 90, 180))
            )
            decoded = decode_png_input(png_path.read_bytes())
            facts["rgba_content_digest"] = fnv1a64(decoded.rgba_bytes)
            rgba_path.write_bytes(decoded.rgba_bytes)
        elif fault == "rgba_sidecar":
            rgba_path.write_bytes(
                rgba_path.read_bytes()[:-4] + bytes((180, 70, 30, 255))
            )
        else:
            altered = list(PREPARED_PIXELS)
            altered[-1] = (
                (180, 70, 30, 255)
                if fault == "last_pixel"
                else (
                    (1, 0, 0, 0)
                    if fault == "transparent_hidden_rgb"
                    else (255, 255, 255, 255)
                )
            )
            metadata = PngImagePlugin.PngInfo()
            metadata.add(b"sRGB", b"\x00")
            image = Image.new("RGBA", (5, 4))
            image.putdata(altered)
            image.save(png_path, pnginfo=metadata)
            rgba_path.write_bytes(image.tobytes())
            if fault != "last_pixel":
                facts["rgba_content_digest"] = facts["stored_content_digest"] = fnv1a64(
                    image.tobytes()
                )

    native.fault = tamper
    result = _call(request, services)
    assert result["code"] == code, result
    if fault == "mapping_rejected":
        assert result["details"]["reason"] == "mapping"
    assert len(native.calls) == 1
    assert not files.publications
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"retained destination"
    assert len(files.discarded) == 2
    _clean(files)


@pytest.mark.parametrize(
    "kind",
    ("same_path", "source_symlink", "destination_symlink", "existing_destination"),
)
def test_publication_preflight_protects_source_and_existing_destination(
    preparation, kind
):
    request, services, native, files, source, destination = preparation
    original = source.read_bytes()
    if kind == "same_path":
        request["destination"]["path"] = str(source)
        reason = "source_destination_alias"
    elif kind == "source_symlink":
        source.rename(destination)
        source.symlink_to(destination)
        reason = "source_destination_alias"
    elif kind == "destination_symlink":
        destination.symlink_to(source)
        reason = "destination_not_file"
    else:
        destination.write_bytes(b"retained destination")
        request["destination"]["if_exists"] = "fail"
        reason = "destination_exists"
    previous = destination.read_bytes() if destination.exists() else None
    result = _call(request, services)
    assert result["code"] == "artifact_file_failed"
    assert result["details"]["reason"] == reason
    assert not native.calls and not files.publications
    assert source.read_bytes() == original
    if previous is not None:
        assert destination.read_bytes() == previous
    assert not files.discarded


def test_failed_publication_preserves_originals_and_cleans_stages(
    preparation, monkeypatch
):
    request, services, native, files, source, destination = preparation
    destination.write_bytes(b"retained destination")
    original = source.read_bytes()

    def refuse_replace(*_args):
        raise PermissionError("Publication denied")

    monkeypatch.setattr("spa.adapters.files.os.replace", refuse_replace)
    result = _call(request, services)
    assert result["code"] == "artifact_file_failed"
    assert result["details"]["reason"] == "publication_failed"
    assert len(native.calls) == 1
    assert files.publications == [destination]
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"retained destination"
    assert len(files.discarded) == 2
    _clean(files)


@pytest.mark.parametrize(
    "change",
    (
        "empty_automatic_crop",
        "crop_outside_source",
        "zero_derived_size",
        "derived_size_overflow",
        "placement_clips",
    ),
)
def test_invalid_derived_geometry_rejects_before_native_and_publication(
    preparation, change
):
    request, services, native, files, source, destination = preparation
    spec = request["specification"]
    if change == "empty_automatic_crop":
        _png(source, pixels=[(44, 11, 66, 127)] * 6)
        spec["crop"] = {"kind": "automatic"}
    elif change == "crop_outside_source":
        spec["crop"]["rectangle"]["x"] = 1
    elif change == "zero_derived_size":
        spec["resize"] = {"kind": "scale", "factor": 0.1}
        spec["rounding"] = "floor"
    elif change == "derived_size_overflow":
        spec["resize"] = {"kind": "scale", "factor": 65536.0}
    else:
        spec["alignment"]["position"] = {"x": 0, "y": 0}
    destination.write_bytes(b"retained destination")
    original = source.read_bytes()
    result = _call(request, services)
    assert result["code"] == "preparation_rejected"
    assert result["details"]["reason"] == "geometry"
    assert not native.calls and not files.publications
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"retained destination"
    assert not files.discarded


@pytest.mark.parametrize(
    ("rounding", "negative", "positive"),
    [
        ("toward-zero", (-1, -1), (1, 1)),
        ("floor", (-2, -2), (1, 1)),
        ("ceil", (-1, -1), (2, 2)),
        ("nearest-away-from-zero", (-1, -2), (1, 2)),
    ],
)
def test_rounding_uses_actual_axis_ratios_and_reports_outside_anchors(
    preparation, rounding, negative, positive
):
    request, services, native, _files, source, _destination = preparation
    # A transparent explicit crop isolates application-owned geometric facts from
    # native resampling; this replay's whole output is independently known RGBA0.
    _png(source, pixels=[(44, 11, 66, 0)] * 6)
    native.pixels = [(0, 0, 0, 0)] * 20
    spec = request["specification"]
    spec["resize"] = {"kind": "size", "width": 4, "height": 3}
    spec["rounding"] = rounding
    spec["anchors"] = [
        {"name": "origin", "x": 0, "y": 0},
        {"name": "negative", "x": -1, "y": -1},
        {"name": "positive", "x": 1, "y": 1},
        {"name": "outside_canvas", "x": 30, "y": 20},
    ]
    spec["alignment"] = {"primary_anchor": "origin", "position": {"x": 0, "y": 0}}
    result = _call(request, services)
    assert result["status"] == "success", result
    geometry = result["reproduction"]["geometry"]
    assert geometry["resized"] == {"width": 4, "height": 3}
    assert geometry["offset"] == {"x": 0, "y": 0}
    assert geometry["anchors"] == [
        {"name": "origin", "x": 0, "y": 0},
        {"name": "negative", "x": negative[0], "y": negative[1]},
        {"name": "positive", "x": positive[0], "y": positive[1]},
        {"name": "outside_canvas", "x": 40, "y": 30},
    ]
    assert result["reproduction"]["content"]["alpha_min"] == 0
    assert result["reproduction"]["content"]["alpha_max"] == 0


@pytest.mark.parametrize(
    ("rounding", "resized", "negative", "positive"),
    [
        ("toward-zero", 3, -1, 4),
        ("floor", 3, -2, 4),
        ("ceil", 4, -2, 6),
        ("nearest-away-from-zero", 4, -2, 6),
    ],
)
def test_uniform_resize_reports_rounded_dimensions_and_crop_relative_anchors(
    preparation, rounding, resized, negative, positive
):
    request, services, native, _files, source, _destination = preparation
    _png(source, pixels=[(44, 11, 66, 0)] * 6)
    native.pixels = [(0, 0, 0, 0)] * 20
    spec = request["specification"]
    spec["crop"]["rectangle"] = {"x": 1, "y": 0, "width": 2, "height": 2}
    spec["resize"] = {"kind": "scale", "factor": 1.75}
    spec["rounding"] = rounding
    spec["anchors"] = [
        {"name": "origin", "x": 1, "y": 0},
        {"name": "outside_crop", "x": 0, "y": -1},
        {"name": "outside_source", "x": 4, "y": 3},
    ]
    spec["alignment"] = {"primary_anchor": "origin", "position": {"x": 0, "y": 0}}
    result = _call(request, services)
    assert result["status"] == "success", result
    geometry = result["reproduction"]["geometry"]
    assert geometry["crop"] == {"x": 1, "y": 0, "width": 2, "height": 2}
    assert geometry["resized"] == {"width": resized, "height": resized}
    assert geometry["anchors"] == [
        {"name": "origin", "x": 0, "y": 0},
        {"name": "outside_crop", "x": negative, "y": negative},
        {"name": "outside_source", "x": positive, "y": positive},
    ]


@pytest.mark.parametrize("coordinate", (True, 0.5, -(2**31) - 1, 2**31))
def test_source_anchors_follow_strict_integer_point_bounds(preparation, coordinate):
    request, services, native, files, _source, _destination = preparation
    request["specification"]["anchors"][0]["x"] = coordinate
    result = _call(request, services)
    assert result["code"] == "invalid_request"
    assert not native.calls and not files.publications


@pytest.mark.parametrize(
    ("coordinate", "placement", "accepted"),
    [(-(2**31), 1, True), (2**31 - 1, 1, True), (2**31 - 1, 2, False)],
)
def test_anchor_bounds_apply_after_crop_resize_and_placement(
    preparation, coordinate, placement, accepted
):
    request, services, native, files, source, _destination = preparation
    _png(source, pixels=[(44, 11, 66, 0)] * 6)
    native.pixels = [(0, 0, 0, 0)] * 20
    spec = request["specification"]
    spec["crop"]["rectangle"] = {"x": 1, "y": 1, "width": 2, "height": 1}
    spec["resize"] = {"kind": "size", "width": 2, "height": 1}
    spec["anchors"] = [
        {"name": "origin", "x": 1, "y": 1},
        {"name": "outside", "x": coordinate, "y": coordinate},
    ]
    spec["alignment"] = {
        "primary_anchor": "origin",
        "position": {"x": placement, "y": placement},
    }
    result = _call(request, services)
    if accepted:
        assert result["status"] == "success", result
        assert result["reproduction"]["geometry"]["offset"] == {"x": 1, "y": 1}
        assert result["reproduction"]["geometry"]["anchors"] == [
            {"name": "origin", "x": 1, "y": 1},
            {"name": "outside", "x": coordinate, "y": coordinate},
        ]
    else:
        assert result["code"] == "preparation_rejected"
        assert result["details"]["reason"] == "geometry"
        assert not native.calls and not files.publications


def test_source_alias_is_checked_again_before_publication(preparation):
    request, services, native, files, source, destination = preparation
    original_path = source.with_name("retained-source.png")
    source.rename(original_path)
    source.symlink_to(original_path)
    original = original_path.read_bytes()
    destination.write_bytes(b"retained destination")

    def retarget_source(_facts, _png_path, _rgba_path):
        source.unlink()
        source.symlink_to(destination)

    native.fault = retarget_source
    result = _call(request, services)
    assert result["code"] == "artifact_file_failed"
    assert result["details"]["reason"] == "source_destination_alias"
    assert len(native.calls) == 1 and not files.publications
    assert original_path.read_bytes() == original
    assert destination.read_bytes() == b"retained destination"
    assert len(files.discarded) == 2
    _clean(files)
