"""Installed PNG Export against a real Aseprite executable."""

import hashlib
import json
import os
import struct
from pathlib import Path

import pytest
from jsonschema import validate
from PIL import Image, ImageCms

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run
from tests.support import export_image_choices, isolated_wheel_cli, source_sprite, spa

pytestmark = pytest.mark.e2e


def test_export_frame_as_verified_visible_rgb_png(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path)
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "image.png"
    request = export_image_choices(source, destination, frame_number=2)

    result = expect_success("export image", request)
    validate(
        result, json.loads(spa("export", "image", "--schema").stdout)["result_schema"]
    )
    assert result["destination"] == request["destination"]
    assert result["frame_number"] == 2
    assert result["width"] == 3 and result["height"] == 2
    assert result["color_mode"] == "rgb"
    assert result["export_image_area"] == {
        "kind": "canvas",
        "rectangle": {"x": 0, "y": 0, "width": 3, "height": 2},
        "slice_index": None,
        "slice_name": None,
        "key_frame_number": None,
    }
    assert result["layer_composition"] == {"mode": "visible"}
    assert result["color_profile"] == "srgb"
    assert result["alpha_channel"] == {
        "present": True,
        "minimum": 0,
        "maximum": 128,
    }
    assert result["artifact"]["path"] == str(destination)
    assert result["artifact"]["role"] == "image"
    assert result["artifact"]["format"] == "png"
    assert result["artifact"]["media_type"] == "image/png"
    assert result["artifact"]["byte_size"] == destination.stat().st_size
    assert (
        result["artifact"]["sha256"]
        == hashlib.sha256(destination.read_bytes()).hexdigest()
    )
    with Image.open(destination) as image:
        image.load()
        assert image.size == (3, 2)
        assert image.convert("RGBA").getpixel((1, 0)) == (17, 34, 51, 128)
        assert image.convert("RGBA").getpixel((0, 0)) == (0, 0, 0, 0)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_sha


def test_export_opaque_rgb_without_color_profile(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(
        runtime, tmp_path, "rgb_profile_alpha.lua", profile="none", alpha="opaque"
    )
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "opaque.png"
    request = export_image_choices(source, destination)

    result = expect_success("export image", request)
    assert result["color_profile"] == "none"
    assert result["alpha_channel"] == {
        "present": True,
        "minimum": 255,
        "maximum": 255,
    }
    with Image.open(destination) as image:
        image.load()
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (11, 22, 33, 255)
        assert image.getpixel((1, 0)) == (44, 55, 66, 255)
        assert "srgb" not in image.info
        assert "icc_profile" not in image.info
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_sha


def test_export_fully_transparent_rgb_preserves_alpha(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(
        runtime, tmp_path, "rgb_profile_alpha.lua", profile="srgb", alpha="transparent"
    )
    destination = tmp_path / "transparent.png"

    result = expect_success("export image", export_image_choices(source, destination))
    assert result["color_profile"] == "srgb"
    assert result["alpha_channel"] == {
        "present": True,
        "minimum": 0,
        "maximum": 0,
    }
    with Image.open(destination) as image:
        image.load()
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (0, 0, 0, 0)
        assert image.getpixel((1, 0)) == (0, 0, 0, 0)


def test_export_opaque_background_preserves_rgb_values(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path, "rgb_background.lua")
    destination = tmp_path / "background.png"

    result = expect_success("export image", export_image_choices(source, destination))
    assert result["alpha_channel"] == {
        "present": False,
        "minimum": 255,
        "maximum": 255,
    }
    with Image.open(destination) as image:
        image.load()
        assert image.mode == "RGB"
        assert image.getpixel((0, 0)) == (10, 20, 30)
        assert image.getpixel((1, 0)) == (40, 50, 60)


@pytest.mark.parametrize("mode", ["grayscale", "indexed"])
def test_export_preserves_grayscale_and_indexed_source_color_modes(
    tmp_path: Path, runtime: RuntimeObservation, mode: str
) -> None:
    source = source_sprite(runtime, tmp_path, "rgb_profile_alpha.lua", mode=mode)
    destination = tmp_path / "preserved.png"

    result = expect_success("export image", export_image_choices(source, destination))
    assert result["source_color_mode"] == mode
    assert result["color_mode"] == mode
    assert result["composition_color_mode"] == "preserve"
    with Image.open(destination) as image:
        image.load()
        assert image.mode == ("LA" if mode == "grayscale" else "P")
        assert image.convert("RGBA").getpixel((0, 0)) == (
            (90, 90, 90, 127) if mode == "grayscale" else (11, 22, 33, 127)
        )
        assert image.convert("RGBA").getpixel((1, 0))[3] == 0
    assert not list(tmp_path.glob("*.staged.png"))
    assert not list(tmp_path.glob("*.staged.rgba"))


@pytest.mark.parametrize("arrangement", ["visible", "hidden_layer", "hidden_group"])
def test_export_composes_visible_tilemap_image(
    tmp_path: Path, runtime: RuntimeObservation, arrangement: str
) -> None:
    source = source_sprite(
        runtime, tmp_path, "rgb_tilemap.lua", arrangement=arrangement
    )
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "tilemap.png"
    request = export_image_choices(source, destination)
    schema = json.loads(spa("export", "image", "--schema").stdout)
    validate(request, schema["request_schema"])

    result = expect_success("export image", request)
    validate(result, schema["result_schema"])
    assert result["layer_composition"] == {"mode": "visible"}
    with Image.open(destination) as image:
        image.load()
        assert image.convert("RGBA").getpixel((0, 0)) == (
            (250, 0, 0, 255) if arrangement == "visible" else (0, 0, 0, 0)
        )
    assert not list(tmp_path.glob("*.staged.png"))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


def test_export_rejects_unlisted_icc_source_before_encoding(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    icc_file = tmp_path / "profile.icc"
    icc_file.write_bytes(
        ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    )
    source = source_sprite(
        runtime,
        tmp_path,
        "rgb_profile_alpha.lua",
        profile="icc",
        icc_file=str(icc_file),
    )
    destination = tmp_path / "unsupported.png"

    outcome = run("export image", export_image_choices(source, destination))

    assert outcome.returncode != 0
    assert outcome.envelope["code"] == "export_image_invalid"
    assert outcome.envelope["details"]["reason"] == "color_profile"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))


def test_export_rejects_gamma_profile_before_encoding(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path, "rgb_profile_alpha.lua")
    payload = bytearray(source.read_bytes())
    chunk_at = 128 + 16
    while chunk_at + 6 <= len(payload):
        chunk_size, chunk_type = struct.unpack_from("<IH", payload, chunk_at)
        assert chunk_size >= 6
        if chunk_type == 0x2007:
            struct.pack_into("<HHI", payload, chunk_at + 6, 0, 1, 65536)
            break
        chunk_at += chunk_size
    else:
        pytest.fail("Aseprite fixture did not contain a Color Profile chunk")
    source.write_bytes(payload)
    destination = tmp_path / "unsupported.png"

    outcome = run("export image", export_image_choices(source, destination))

    assert outcome.returncode != 0
    assert outcome.envelope["code"] == "kernel_execution_failed"
    assert outcome.envelope["details"]["reason"].endswith(
        ": unsupported Source Sprite Color Profile"
    )
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))


def test_export_replaces_existing_file_when_policy_is_replace(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path)
    destination = tmp_path / "image.png"
    destination.write_bytes(b"existing artifact")
    original = destination.read_bytes()

    result = expect_success(
        "export image", export_image_choices(source, destination, if_exists="replace")
    )
    assert result["destination"] == {
        "path": str(destination),
        "if_exists": "replace",
    }
    assert destination.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert destination.read_bytes() != original


def test_export_rejects_out_of_range_frame_before_encoding(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path)
    destination = tmp_path / "out-of-range.png"

    outcome = run(
        "export image", export_image_choices(source, destination, frame_number=3)
    )

    assert outcome.returncode != 0
    assert outcome.envelope["code"] == "export_image_invalid"
    assert outcome.envelope["details"]["reason"] == "frame_number"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))


def test_export_uses_native_visible_group_composition(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path, "group_composition.lua")
    destination = tmp_path / "group.png"

    expect_success("export image", export_image_choices(source, destination))
    with Image.open(destination) as image:
        image.load()
        assert image.convert("RGBA").getpixel((0, 0)) == (0, 0, 200, 128)


def test_export_reports_normalized_destination(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path)
    destination = tmp_path / "unused" / ".." / "normalized.png"
    normalized = tmp_path / "normalized.png"

    result = expect_success("export image", export_image_choices(source, destination))
    assert result["destination"]["path"] == str(normalized)
    assert result["artifact"]["path"] == str(normalized)
    assert normalized.is_file()


def test_export_cannot_publish_when_source_is_missing(tmp_path: Path) -> None:
    source = tmp_path / "missing.aseprite"
    destination = tmp_path / "missing-source.png"

    outcome = run("export image", export_image_choices(source, destination))

    assert outcome.returncode != 0
    assert outcome.envelope["code"] == "kernel_execution_failed"
    assert outcome.envelope["details"]["reason"].endswith(
        ": could not open Source Sprite"
    )
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))
    assert not list(tmp_path.glob("*.staged.rgba"))


def test_wheel_installed_cli_exports_verified_image(
    tmp_path: Path, runtime: RuntimeObservation, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed_cli = isolated_wheel_cli(tmp_path, monkeypatch)
    source = source_sprite(runtime, tmp_path)
    destination = tmp_path / "wheel.png"

    exported = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(
            export_image_choices(
                source,
                destination,
                frame_number=2,
                aseprite=os.environ["SPA_TEST_ASEPRITE"],
            )
        ),
        executable=installed_cli,
    )

    assert exported.returncode == 0, exported.stdout
    result = json.loads(exported.stdout)
    assert result["artifact"]["path"] == str(destination)
    with Image.open(destination) as image:
        image.load()
        assert image.convert("RGBA").getpixel((1, 0)) == (17, 34, 51, 128)
