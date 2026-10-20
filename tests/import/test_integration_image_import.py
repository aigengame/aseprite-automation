"""Public import refuses unsupported inputs and unverified native evidence."""

import json
from functools import partial
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from PIL import Image, ImageCms

from spa.adapters.aseprite.aseprite import invoke, probe
from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png_input import decode_png_input
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import PROBE_RESOURCES
from spa.authoring.raster.image_import import IMAGE_IMPORT_OPERATIONS
from spa.contracts.digest import fnv1a64
from spa.contracts.ports import OperationServices
from tests.host_permissions import symlink_creation_permission
from tests.support import fake_probe_response, probe_answer, runtime_observation

from .support import ObservedTargetFiles, assert_unpublished, indexed_png


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


def _call(request, target_files=None):
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
            target_files=target_files or LocalTargetFiles(),
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


@pytest.mark.parametrize("alias", ["direct", "symlink_chain"])
def test_raster_alias_of_target_rejects_before_native(tmp_path, alias):
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"untouched Source")
    target = tmp_path / "input.aseprite"
    Image.new("RGBA", (2, 1), (17, 31, 53, 128)).save(target, format="PNG")
    original_png = target.read_bytes()
    raster = target
    if alias == "symlink_chain":
        raster, intermediate = tmp_path / "input.png", tmp_path / "intermediate.png"
        with symlink_creation_permission():
            intermediate.symlink_to(target.name)
            raster.symlink_to(intermediate.name)
    request = {
        **_request(tmp_path),
        "target_sprite_file": str(target),
        "raster_file": str(raster),
    }
    before = {item.name for item in tmp_path.iterdir()}
    files = ObservedTargetFiles()

    failure = _call(request, files)

    assert failure["code"] == "image_import_incompatible", failure
    assert failure["details"]["reason"] == "output_alias"
    assert source.read_bytes() == b"untouched Source"
    assert raster.read_bytes() == target.read_bytes() == original_png
    assert files.stages == files.commits == files.discards == []
    assert {item.name for item in tmp_path.iterdir()} == before


# The Kernel result that real Aseprite 1.3.18.5 gave once for the inputs of `_replay`:
# a 2x1 PNG at (-1, 1) in the empty Cel at Layer 1, Frame 2 of a 3x2 Sprite with 3
# Frames. The result has no paths.
_BOUNDS = {"x": -1, "y": 1, "width": 2, "height": 1}
_PALETTE = [(0, 0, 0, 0), (200, 20, 40, 255), (10, 80, 160, 128), (17, 31, 53, 255)]


def _color(red, green, blue, alpha):
    return {"red": red, "green": green, "blue": blue, "alpha": alpha}


def _cel_state(**state):
    return {
        "layer_path": [1],
        "frame_number": 2,
        "is_background": False,
        "is_tilemap": False,
        "linked_cels": [],
        **state,
    }


def _native_result(indexed):
    mode = "indexed" if indexed else "rgb"
    stored, rgba = (
        ("082f2307b4e88e77", "7c430f3556d0bd65")
        if indexed
        else ("1ea0cbcc2ca87f05", "1ea0cbcc2ca87f05")
    )
    palette = _PALETTE if indexed else _PALETTE[:1]
    return {
        "before": _cel_state(
            exists=False,
            content="absent",
            image_bounds=None,
            opacity=None,
            position=None,
            z_index=None,
        ),
        "before_cel_count": 0,
        # Each bounds field gets its own copy, so a corruption changes only its field
        # and only this result.
        "cel": _cel_state(
            exists=True,
            content="nonempty",
            image_bounds=dict(_BOUNDS),
            opacity=255,
            position={"x": -1, "y": 1},
            z_index=0,
        ),
        "color_profile": {"kind": "none", "icc_identity": None},
        "effective_palette": {
            "frame_number": 2,
            "palette_frame_number": 1,
            "palette_size": 4,
            "indexes": [{"index": 1, "color": _color(*_PALETTE[1])}],
        }
        if indexed
        else None,
        "image": {
            "color_mode": mode,
            "width": 2,
            "height": 1,
            "stored_content_digest": {"algorithm": "fnv1a64", "value": stored},
            "rgba_content_digest": {"algorithm": "fnv1a64", "value": rgba},
        },
        "persisted_reopen_verified": True,
        "sprite": {
            "cels": [
                {
                    "layer_path": [1],
                    "frame_number": 2,
                    "bounds": dict(_BOUNDS),
                    "opacity": 255,
                    "z_index": 0,
                }
            ],
            "frames": [{"frame_number": n, "duration_ms": 100} for n in (1, 2, 3)],
            "layers": [
                {
                    "name": "Destination",
                    "path": [1],
                    "layer_uuid": None,
                    "children": [],
                    "blend_mode": "normal",
                    "opacity": 255,
                    "is_background": False,
                    "is_collapsed": False,
                    "is_continuous": False,
                    "is_editable": True,
                    "is_group": False,
                    "is_image": True,
                    "is_reference": False,
                    "is_tilemap": False,
                    "is_transparent": True,
                    "is_visible": True,
                }
            ],
            "metadata": {
                "width": 3,
                "height": 2,
                "color_mode": mode,
                "transparent_color_index": 0,
                "frame_count": 3,
                "layer_count": 1,
                "cel_count": 1,
                "palette_count": 1,
                "slice_count": 0,
                "tag_count": 0,
                "tileset_count": 0,
                "grid_bounds": {"x": 0, "y": 0, "width": 16, "height": 16},
                "pixel_ratio": {"width": 1, "height": 1},
                "use_layer_uuids": False,
            },
            "palettes": [
                {
                    "frame_number": 1,
                    "entries": [
                        {"index": index, "color": _color(*color)}
                        for index, color in enumerate(palette)
                    ],
                }
            ],
            "slices": [],
            "tags": [],
            "tilesets": [],
        },
        "transparent_index": 0 if indexed else None,
    }


def _tamper(result, corruption):
    if corruption in ("stored_digest", "rgba_digest"):
        result["image"][
            "stored_content_digest"
            if corruption == "stored_digest"
            else "rgba_content_digest"
        ]["value"] = "0" * 16
    elif corruption == "geometry":
        result["cel"]["image_bounds"]["width"] += 1
    elif corruption == "frame":
        result["cel"]["frame_number"] = result["before"]["frame_number"] = 1
    elif corruption == "layer_path":
        result["cel"]["layer_path"] = result["before"]["layer_path"] = [2]
    elif corruption == "sprite_cel":
        result["sprite"]["cels"][0]["bounds"]["width"] += 1
    elif corruption == "persisted":
        result["persisted_reopen_verified"] = False
    elif corruption == "palette_color":
        result["effective_palette"]["indexes"][0]["color"]["red"] += 1
    elif corruption == "palette_frame":
        result["effective_palette"]["palette_frame_number"] = 3
    elif corruption == "mask_collision":
        result["transparent_index"] = 1
    elif corruption == "mask_fact":
        result["transparent_index"] = 3


def _replay(tmp_path, *, indexed, corruption=None):
    """Import through a controlled Aseprite that replays the recorded Kernel result.

    The replay writes a staged Sprite, as the Kernel does before its response.
    """
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    source.write_bytes(b"Source Sprite")
    target.write_bytes(b"existing Target")
    if indexed:
        indexed_png(raster, [1, 1])
    else:
        Image.new("RGBA", (2, 1), (17, 31, 53, 128)).save(raster)
    original = source.read_bytes(), raster.read_bytes(), target.read_bytes()
    result = _native_result(indexed)
    _tamper(result, corruption)
    binary = fake_probe_response(
        tmp_path,
        probe_answer(),
        kernel_response=json.dumps(
            {"kernel_protocol_version": 1, "status": "ok", "result": result}
        ),
    )
    files = ObservedTargetFiles()
    calls = []

    def native(observation, handler, payload, timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"staged Sprite")
        calls.append(handler.name)
        return invoke(observation, handler, payload, timeout)

    request = {
        **_request(tmp_path),
        "aseprite": str(binary),
        "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
        "position": {"x": -1, "y": 1},
    }
    outcome = dispatch(
        IMAGE_IMPORT_OPERATIONS[0],
        json.dumps(request),
        {},
        OperationServices(
            probe_runtime=partial(probe, resources=PROBE_RESOURCES),
            invoke_kernel=native,
            target_files=files,
            artifact_files=LocalArtifactFiles(),
            decode_png_input=decode_png_input,
        ),
        FAILURE_CODES,
    ).model_dump(mode="json")
    assert calls == ["image_import"]
    return outcome, (source, raster, target, original, files)


@pytest.mark.parametrize("indexed", [False, True])
def test_recorded_native_success_publishes(tmp_path, indexed):
    result, (source, raster, target, original, files) = _replay(
        tmp_path, indexed=indexed
    )
    assert result["status"] == "success", result
    assert result["image"] == _native_result(indexed)["image"]
    assert target.read_bytes() == b"staged Sprite"
    assert (source.read_bytes(), raster.read_bytes()) == original[:2]
    assert len(files.stages) == 1
    assert files.commits == files.stages == files.discards


@pytest.mark.parametrize(
    "corruption",
    [
        "stored_digest",
        "rgba_digest",
        "geometry",
        "frame",
        "layer_path",
        "sprite_cel",
        "persisted",
        "palette_color",
        "palette_frame",
        "mask_collision",
        "mask_fact",
    ],
)
def test_tampered_native_success_cannot_publish(tmp_path, corruption):
    indexed = corruption.startswith(("palette", "mask"))
    result, (source, raster, target, original, files) = _replay(
        tmp_path, indexed=indexed, corruption=corruption
    )
    assert result.get("code") == "kernel_response_invalid", result
    assert not files.commits
    assert_unpublished(source, raster, target, original, files)
