"""Public import preflight refuses unsupported inputs before native mutation."""

import json

import pytest
from jsonschema import Draft202012Validator
from PIL import Image, ImageCms

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png_input import decode_png_input
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.authoring.raster.image_import import IMAGE_IMPORT_OPERATIONS
from spa.contracts.digest import fnv1a64
from spa.contracts.ports import OperationServices
from tests.support import runtime_observation


def _unused(*args):
    raise AssertionError("Invalid input reached native execution")


def _request(tmp_path):
    return {
        "source_sprite_file": str(tmp_path / "source.aseprite"),
        "target_sprite_file": str(tmp_path / "target.aseprite"),
        "raster_file": str(tmp_path / "input.png"),
        "in_place": False,
        "overwrite": True,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "position": {"x": 0, "y": 0},
    }


def _call(request):
    return dispatch(
        IMAGE_IMPORT_OPERATIONS[0],
        json.dumps(request),
        {},
        OperationServices(
            probe_runtime=lambda _: runtime_observation(
                "aseprite_sprite_inspection",
                "aseprite_cel_lifecycle",
                "aseprite_assign_color_profile",
                "aseprite_palette_entries",
            ),
            invoke_kernel=_unused,
            target_files=LocalTargetFiles(),
            artifact_files=LocalArtifactFiles(),
            decode_png_input=decode_png_input,
        ),
        FAILURE_CODES,
    ).model_dump(mode="json")


@pytest.mark.parametrize(
    "change",
    [
        {"position": {"x": 32768, "y": 0}},
        {"position": {"x": -32769, "y": 0}},
        {"position": {"x": 0.5, "y": 0}},
        {"position": {"x": True, "y": 0}},
        {"raster_file": "invalid\0.png"},
        {"raster_file": "invalid\n.png"},
        {"replace": True},
        {"convert": "rgb"},
        {"position": None},
    ],
)
def test_invalid_request_is_rejected_before_native(tmp_path, change):
    failure = _call({**_request(tmp_path), **change})
    assert failure["code"] == "invalid_request"
    Draft202012Validator(
        IMAGE_IMPORT_OPERATIONS[0].schema(FAILURE_CODES).failure_schema
    ).validate(failure)


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("missing", "unreadable"),
        ("malformed", "invalid_png"),
        ("grayscale", "invalid_png"),
        ("icc", "unsupported_profile"),
    ],
)
def test_encoded_input_failure_preserves_existing_target(tmp_path, kind, reason):
    source, target, png = (
        tmp_path / name for name in ("source.aseprite", "target.aseprite", "input.png")
    )
    source.write_bytes(b"untouched Source")
    target.write_bytes(b"untouched Target")
    if kind == "malformed":
        png.write_bytes(b"not PNG")
    elif kind == "grayscale":
        Image.new("L", (1, 1)).save(png)
    elif kind == "icc":
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        Image.new("RGB", (1, 1)).save(png, icc_profile=profile)
    failure = _call(_request(tmp_path))
    assert failure["code"] == "image_import_incompatible"
    assert failure["details"]["reason"] == reason
    assert source.read_bytes() == b"untouched Source"
    assert target.read_bytes() == b"untouched Target"
    assert not list(tmp_path.glob("*.staged.aseprite"))
    Draft202012Validator(
        IMAGE_IMPORT_OPERATIONS[0].schema(FAILURE_CODES).failure_schema
    ).validate(failure)


def test_import_descriptor_keeps_standalone_mutation_contract():
    descriptor = IMAGE_IMPORT_OPERATIONS[0]
    assert descriptor.execution_kind == "mutation"
    assert descriptor.plan_eligible is False
    schema = descriptor.schema(FAILURE_CODES)
    Draft202012Validator.check_schema(schema.request_schema)
    Draft202012Validator.check_schema(schema.result_schema)


def test_native_comparison_digest_uses_known_fnv_vectors():
    assert fnv1a64(b"") == "cbf29ce484222325"
    assert fnv1a64(b"hello") == "a430d84680aabd0b"
