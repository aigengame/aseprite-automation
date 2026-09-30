"""Installed PNG Export against a real Aseprite executable."""

import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, validate
from PIL import Image, ImageCms

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import spa

pytestmark = pytest.mark.e2e


def _source(
    tmp_path: Path,
    fixture_name: str = "rgb_frames.lua",
    **params: str,
) -> Path:
    source = tmp_path / "source.aseprite"
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]),
        PROBE_RESOURCES,
    )
    fixture = Path(__file__).parent / "fixtures" / fixture_name
    with tempfile.TemporaryDirectory(prefix="spa-export-fixture-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={source}",
                *[
                    argument
                    for name, value in params.items()
                    for argument in ("--script-param", f"{name}={value}")
                ],
                "--script",
                str(fixture),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr
    assert source.is_file()
    return source


def _request(
    source: Path,
    destination: Path,
    *,
    frame_number: int = 1,
    if_exists: str = "fail",
) -> dict[str, object]:
    return {
        "source_sprite_file": str(source),
        "destination": {"path": str(destination), "if_exists": if_exists},
        "frame_number": frame_number,
        "color_mode": "preserve",
        "color_profile": "preserve",
        "transparency": "preserve",
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }


def test_export_frame_as_verified_visible_rgb_png(tmp_path: Path) -> None:
    source = _source(tmp_path)
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "image.png"
    request = _request(source, destination, frame_number=2)

    run = spa("export", "image", "--input-json", json.dumps(request))

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(
        result, json.loads(spa("export", "image", "--schema").stdout)["result_schema"]
    )
    assert result["destination"] == request["destination"]
    assert result["frame_number"] == 2
    assert result["width"] == 3 and result["height"] == 2
    assert result["color_mode"] == "rgb"
    assert result["export_image_area"] == "canvas"
    assert result["layer_composition"] == "visible"
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


def test_export_rejects_destination_traversed_by_source_alias(tmp_path: Path) -> None:
    native_source = _source(tmp_path)
    destination = tmp_path / "image.png"
    shutil.copyfile(native_source, destination)
    source = tmp_path / "linked.aseprite"
    source.symlink_to(destination)
    original = hashlib.sha256(source.read_bytes()).hexdigest()

    run = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(_request(source, destination, if_exists="replace")),
    )

    assert run.returncode != 0
    failure = json.loads(run.stdout)
    assert failure["code"] == "artifact_file_failed"
    assert failure["details"]["reason"] == "source_destination_alias"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == original


def test_export_reports_unverifiable_source_destination_identity(
    tmp_path: Path,
) -> None:
    native_source = _source(tmp_path)
    private = tmp_path / "private"
    private.mkdir()
    source = private / "source.aseprite"
    shutil.copyfile(native_source, source)
    destination = private / "image.png"
    os.link(source, destination)
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    private.chmod(0o333)
    try:
        try:
            os.listdir(private)
        except PermissionError:
            pass
        else:
            pytest.skip("cannot reproduce an unlistable directory")
        run = spa(
            "export",
            "image",
            "--input-json",
            json.dumps(_request(source, destination, if_exists="replace")),
        )
    finally:
        private.chmod(0o700)

    assert run.returncode != 0 and run.stdout
    failure = json.loads(run.stdout)
    assert failure["code"] == "artifact_file_failed"
    assert failure["details"]["reason"] == "source_destination_identity_unverified"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == original


def test_export_opaque_rgb_without_color_profile(tmp_path: Path) -> None:
    source = _source(tmp_path, "rgb_profile_alpha.lua", profile="none", alpha="opaque")
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "opaque.png"
    request = _request(source, destination)

    run = spa("export", "image", "--input-json", json.dumps(request))

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
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


def test_export_fully_transparent_rgb_preserves_alpha(tmp_path: Path) -> None:
    source = _source(
        tmp_path, "rgb_profile_alpha.lua", profile="srgb", alpha="transparent"
    )
    destination = tmp_path / "transparent.png"

    run = spa(
        "export", "image", "--input-json", json.dumps(_request(source, destination))
    )

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
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


def test_export_opaque_background_preserves_rgb_values(tmp_path: Path) -> None:
    source = _source(tmp_path, "rgb_background.lua")
    destination = tmp_path / "background.png"

    run = spa(
        "export", "image", "--input-json", json.dumps(_request(source, destination))
    )

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["alpha_channel"] == {
        "present": True,
        "minimum": 255,
        "maximum": 255,
    }
    with Image.open(destination) as image:
        image.load()
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (10, 20, 30, 255)
        assert image.getpixel((1, 0)) == (40, 50, 60, 255)


@pytest.mark.parametrize("mode", ["grayscale", "indexed"])
def test_export_rejects_unsupported_source_color_modes(
    tmp_path: Path, mode: str
) -> None:
    source = _source(tmp_path, "rgb_profile_alpha.lua", mode=mode)
    destination = tmp_path / "unsupported.png"

    run = spa(
        "export", "image", "--input-json", json.dumps(_request(source, destination))
    )

    assert run.returncode != 0
    assert json.loads(run.stdout)["code"] == "kernel_execution_failed"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))


@pytest.mark.parametrize("arrangement", ["visible", "hidden_layer", "hidden_group"])
def test_export_rejects_tilemap_image_before_encoding(
    tmp_path: Path, arrangement: str
) -> None:
    source = _source(tmp_path, "rgb_tilemap.lua", arrangement=arrangement)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "unsupported.png"
    request = _request(source, destination)
    schema = json.loads(spa("export", "image", "--schema").stdout)
    validate(request, schema["request_schema"])

    run = spa("export", "image", "--input-json", json.dumps(request))

    assert run.returncode != 0
    failure = json.loads(run.stdout)
    validate(failure, schema["failure_schema"])
    assert failure["code"] == "kernel_execution_failed"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


def test_export_rejects_icc_source_before_encoding(tmp_path: Path) -> None:
    icc_file = tmp_path / "profile.icc"
    icc_file.write_bytes(
        ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    )
    source = _source(
        tmp_path, "rgb_profile_alpha.lua", profile="icc", icc_file=str(icc_file)
    )
    destination = tmp_path / "unsupported.png"

    run = spa(
        "export", "image", "--input-json", json.dumps(_request(source, destination))
    )

    assert run.returncode != 0
    assert json.loads(run.stdout)["code"] == "kernel_execution_failed"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))


def test_export_rejects_gamma_profile_before_encoding(tmp_path: Path) -> None:
    source = _source(tmp_path, "rgb_profile_alpha.lua")
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

    run = spa(
        "export", "image", "--input-json", json.dumps(_request(source, destination))
    )

    assert run.returncode != 0
    assert json.loads(run.stdout)["code"] == "kernel_execution_failed"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))


def test_export_requires_explicit_existing_file_policy(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "image.png"
    destination.write_bytes(b"existing artifact")
    original = destination.read_bytes()

    refused = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(_request(source, destination)),
    )

    assert refused.returncode != 0
    refusal = json.loads(refused.stdout)
    assert refusal["code"] == "artifact_file_failed"
    assert refusal["details"]["reason"] == "destination_exists"
    assert destination.read_bytes() == original
    assert not list(tmp_path.glob("*.staged.png"))

    replaced = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(_request(source, destination, if_exists="replace")),
    )

    assert replaced.returncode == 0, replaced.stdout
    result = json.loads(replaced.stdout)
    assert result["destination"] == {
        "path": str(destination),
        "if_exists": "replace",
    }
    assert destination.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert destination.read_bytes() != original


def test_export_rejects_out_of_range_frame_before_encoding(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "out-of-range.png"

    run = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(_request(source, destination, frame_number=3)),
    )

    assert run.returncode != 0
    assert json.loads(run.stdout)["code"] == "kernel_execution_failed"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))


def test_export_uses_native_visible_group_composition(tmp_path: Path) -> None:
    source = _source(tmp_path, "group_composition.lua")
    destination = tmp_path / "group.png"

    run = spa(
        "export", "image", "--input-json", json.dumps(_request(source, destination))
    )

    assert run.returncode == 0, run.stdout
    with Image.open(destination) as image:
        image.load()
        assert image.convert("RGBA").getpixel((0, 0)) == (0, 0, 200, 128)


def test_export_schema_refuses_out_of_slice_choices(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "rejected.png"
    accepted = _request(source, destination)
    schema = json.loads(spa("export", "image", "--schema").stdout)
    validator = Draft202012Validator(schema["request_schema"])
    validator.validate(accepted)
    assert schema["execution_kind"] == "export"
    assert schema["side_effects"] == ["publishes one verified PNG Image Artifact"]

    rejected: list[tuple[str, object]] = [
        ("destination.path", str(tmp_path / "image.jpg")),
        ("destination.path", str(tmp_path / "image.PNG")),
        ("destination.path", str(tmp_path / "image.png") + "\n"),
        ("destination.path", str(tmp_path / "image\r.png")),
        ("destination.path", str(tmp_path / "image\x00.png")),
        ("source_sprite_file", str(source) + "\n"),
        ("source_sprite_file", str(tmp_path / "source\r.aseprite")),
        ("source_sprite_file", str(tmp_path / "source\x00.aseprite")),
        ("destination.if_exists", None),
        ("frame_number", 0),
        ("frame_number", None),
        ("tag", "walk"),
        ("frame_range", [1, 2]),
        ("ignore_empty", True),
        (
            "export_image_area",
            {"kind": "bounds", "x": 0, "y": 0, "width": 1, "height": 1},
        ),
        ("selection", {"kind": "mask"}),
        ("layer_composition", "all"),
        ("include_layers", [[1]]),
        ("color_mode", "grayscale"),
        ("color_profile", "omit"),
        ("transparency", "background"),
        ("palette", {"kind": "quantize"}),
        ("outputs", [str(destination), str(tmp_path / "other.png")]),
        ("format", "png"),
    ]
    for location, value in rejected:
        request = deepcopy(accepted)
        parent, separator, field = location.partition(".")
        target = request[parent] if separator else request
        assert isinstance(target, dict)
        if value is None:
            target.pop(field if separator else parent)
        else:
            target[field if separator else parent] = value
        assert not validator.is_valid(request), location
        run = spa("export", "image", "--input-json", json.dumps(request))
        assert run.returncode == 2, (location, run.stdout)
        failure = json.loads(run.stdout)
        validate(failure, schema["failure_schema"])
        assert failure["code"] == "invalid_request"
        assert not destination.exists()


def test_export_reports_normalized_destination(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "unused" / ".." / "normalized.png"
    normalized = tmp_path / "normalized.png"

    run = spa(
        "export", "image", "--input-json", json.dumps(_request(source, destination))
    )

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["destination"]["path"] == str(normalized)
    assert result["artifact"]["path"] == str(normalized)
    assert normalized.is_file()


def test_export_cannot_publish_when_source_is_missing(tmp_path: Path) -> None:
    source = tmp_path / "missing.aseprite"
    destination = tmp_path / "missing-source.png"

    run = spa(
        "export", "image", "--input-json", json.dumps(_request(source, destination))
    )

    assert run.returncode != 0
    assert json.loads(run.stdout)["code"] == "kernel_execution_failed"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))
    assert not list(tmp_path.glob("*.staged.rgba"))


def test_wheel_installed_cli_exports_verified_image(tmp_path: Path) -> None:
    installed_cli = os.environ.get("SPA_TEST_INSTALLED_CLI")
    if not installed_cli:
        pytest.skip("SPA_TEST_INSTALLED_CLI does not select a wheel-installed CLI")
    source = _source(tmp_path)
    destination = tmp_path / "wheel.png"

    run = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(_request(source, destination, frame_number=2)),
        executable=installed_cli,
    )

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["artifact"]["path"] == str(destination)
    with Image.open(destination) as image:
        image.load()
        assert image.convert("RGBA").getpixel((1, 0)) == (17, 34, 51, 128)
