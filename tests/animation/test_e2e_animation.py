"""Installed animation audit, compare, and preview against native Aseprite."""

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run, run_lua
from tests.support import process_diagnostics, source_sprite

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"


def test_audit_reports_exact_declared_coverage_and_findings(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "coverage.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "animation audit",
        {
            "sprite_file": str(source),
            "from_frame": 1,
            "to_frame": 3,
            "required_cels": [
                {"layer": {"layer_path": [1]}, "frame_number": 3},
            ],
            "duration_bounds": {"minimum_ms": 90, "maximum_ms": 210},
            "non_overlap": [
                {
                    "first_layer": {"layer_path": [1]},
                    "second_layer": {"layer_path": [2]},
                }
            ],
        },
    )
    assert result["complete"] is True
    assert result["scope"] == {"from_frame": 1, "to_frame": 3}
    assert result["required_cels"] == [
        {"layer_path": [1], "frame_number": 3, "exists": False}
    ]
    assert [item["duration_ms"] for item in result["durations"]] == [100, 200, 300]
    assert [item["overlap_pixels"] for item in result["overlaps"]] == [0, 1, 0]
    assert [item["kind"] for item in result["findings"]] == [
        "required_cel_missing",
        "duration_out_of_bounds",
        "layer_overlap",
    ]


def test_audit_allows_undeclared_absent_cel(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "coverage.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "animation audit",
        {
            "sprite_file": str(source),
            "from_frame": 1,
            "to_frame": 3,
            "required_cels": [],
            "non_overlap": [],
        },
    )
    assert result["complete"] is True
    assert result["required_cels"] == []
    assert result["durations"] == []
    assert result["overlaps"] == []
    assert result["findings"] == []


def test_audit_uses_quantized_native_effective_alpha(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "low_opacity.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "animation audit",
        {
            "sprite_file": str(source),
            "from_frame": 1,
            "to_frame": 1,
            "non_overlap": [
                {
                    "first_layer": {"layer_path": [1]},
                    "second_layer": {"layer_path": [2]},
                }
            ],
        },
    )
    assert result["overlaps"][0]["overlap_pixels"] == 0
    assert result["findings"] == []


def test_audit_ignores_hidden_cel_in_declared_pair(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path, "rgb_frames.lua")
    result = expect_success(
        "animation audit",
        {
            "sprite_file": str(source),
            "from_frame": 2,
            "to_frame": 2,
            "non_overlap": [
                {
                    "first_layer": {"layer_path": [1]},
                    "second_layer": {"layer_path": [2]},
                }
            ],
        },
    )
    assert result["overlaps"][0]["overlap_pixels"] == 0
    assert result["findings"] == []


def test_audit_reports_typed_overlap_pixel_limit(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(
        FIXTURES / "coverage.lua", runtime, out=source, width="1024", height="1024"
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    pair = {
        "first_layer": {"layer_path": [1]},
        "second_layer": {"layer_path": [2]},
    }
    outcome = run(
        "animation audit",
        {
            "sprite_file": str(source),
            "from_frame": 1,
            "to_frame": 3,
            "non_overlap": [pair] * 6,
        },
    )
    failure = outcome.envelope
    assert outcome.returncode != 0 and failure["code"] == "audit_limit_exceeded"
    assert failure["details"] == {
        "kind": "operation_limit",
        "unit": "overlap_pixel_checks",
        "requested": 18_874_368,
        "allowed_minimum": 0,
        "allowed_maximum": 16_777_216,
    }


def test_compare_counts_full_canvas_rgba_differences(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path, "rgb_frames.lua")
    request = {"sprite_file": str(source), "earlier_frame": 1, "later_frame": 2}
    different = expect_success("animation compare", request)
    assert different["complete"] is True
    assert different["color_mode"] == "rgb"
    assert different["bounds"] == {"x": 0, "y": 0, "width": 3, "height": 2}
    assert different["differing_pixels"] == 2
    identical_source = source_sprite(
        runtime,
        tmp_path,
        "rgb_profile_alpha.lua",
        profile="none",
        alpha="opaque",
        two_frames="true",
    )
    same = expect_success(
        "animation compare", {**request, "sprite_file": str(identical_source)}
    )
    assert same["differing_pixels"] == 0


def test_preview_publishes_verified_overlay_without_source_mutation(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path, "rgb_frames.lua")
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "preview.png"
    request = {
        "source_sprite_file": str(source),
        "earlier_frame": 1,
        "later_frame": 2,
        "destination": {"path": str(destination), "if_exists": "fail"},
    }
    result = expect_success("animation preview", request)
    assert result["destination"] == request["destination"]
    assert result["artifact"]["path"] == str(destination)
    assert result["artifact"]["role"] == "preview"
    assert result["artifact"]["format"] == "png"
    assert result["artifact"]["media_type"] == "image/png"
    assert result["artifact"]["byte_size"] == destination.stat().st_size
    assert result["width"] == 3 and result["height"] == 2
    assert result["color_mode"] == "rgb"
    assert result["color_profile"] == "srgb"
    assert result["alpha_channel"] == {"present": True, "minimum": 0, "maximum": 128}
    assert (
        result["artifact"]["sha256"]
        == hashlib.sha256(destination.read_bytes()).hexdigest()
    )
    assert result["earlier_frame"] == 1 and result["later_frame"] == 2
    assert result["layer_order"] == ["later", "earlier"]
    assert result["earlier_blend_mode"] == "normal"
    assert result["earlier_opacity"] == 128
    assert result["native_runtime"]["aseprite_version"]
    with Image.open(destination) as image:
        image.load()
        assert image.size == (3, 2)
        assert image.convert("RGBA").getpixel((0, 0)) == (200, 10, 20, 128)
        assert image.convert("RGBA").getpixel((1, 0)) == (17, 34, 51, 128)
        assert image.convert("RGBA").getpixel((2, 0)) == (0, 0, 0, 0)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    assert not list(tmp_path.glob("*.staged.png"))
    assert not list(tmp_path.glob("*.staged.rgba"))


def test_preview_requires_explicit_replacement_intent(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = source_sprite(runtime, tmp_path, "rgb_frames.lua")
    destination = tmp_path / "preview.png"
    destination.write_bytes(b"existing")
    request = {
        "source_sprite_file": str(source),
        "earlier_frame": 1,
        "later_frame": 2,
        "destination": {"path": str(destination), "if_exists": "fail"},
    }
    outcome = run("animation preview", request)
    failure = outcome.envelope
    assert outcome.returncode != 0 and failure["code"] == "artifact_file_failed"
    assert destination.read_bytes() == b"existing"
    expect_success(
        "animation preview",
        {**request, "destination": {"path": str(destination), "if_exists": "replace"}},
    )
    assert destination.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize("alpha", ["opaque", "partial", "transparent"])
def test_preview_decoded_alpha_fixtures(
    tmp_path: Path, runtime: RuntimeObservation, alpha: str
) -> None:
    source = source_sprite(
        runtime,
        tmp_path,
        "rgb_profile_alpha.lua",
        profile="none",
        alpha=alpha,
        two_frames="true",
    )
    destination = tmp_path / "preview.png"
    result = expect_success(
        "animation preview",
        {
            "source_sprite_file": str(source),
            "earlier_frame": 1,
            "later_frame": 2,
            "destination": {"path": str(destination), "if_exists": "fail"},
        },
    )
    assert result["color_profile"] == "none"
    with Image.open(destination) as image:
        image.load()
        rgba = image.convert("RGBA")
        pixels = [rgba.getpixel((x, 0)) for x in range(rgba.width)]
    if alpha == "opaque":
        assert [pixel[3] for pixel in pixels] == [255, 255]
    elif alpha == "transparent":
        assert [pixel[3] for pixel in pixels] == [0, 0]
    else:
        assert 0 < pixels[0][3] < 255
        assert pixels[1][3] == 0


@pytest.mark.parametrize(
    "fixture,params",
    [
        ("rgb_profile_alpha.lua", {"mode": "grayscale"}),
        ("rgb_profile_alpha.lua", {"mode": "indexed"}),
        ("rgb_tilemap.lua", {"arrangement": "hidden_layer"}),
        ("rgb_tilemap.lua", {"arrangement": "hidden_group"}),
    ],
)
def test_compare_and_preview_reject_export_image_input_matrix(
    tmp_path: Path,
    runtime: RuntimeObservation,
    fixture: str,
    params: dict[str, str],
) -> None:
    source = source_sprite(runtime, tmp_path, fixture, two_frames="true", **params)
    destination = tmp_path / "preview.png"
    outcome = run(
        "animation compare",
        {"sprite_file": str(source), "earlier_frame": 1, "later_frame": 2},
    )
    compared = outcome.envelope
    assert outcome.returncode != 0 and compared["code"] == "kernel_execution_failed"
    outcome = run(
        "animation preview",
        {
            "source_sprite_file": str(source),
            "earlier_frame": 1,
            "later_frame": 2,
            "destination": {"path": str(destination), "if_exists": "fail"},
        },
    )
    previewed = outcome.envelope
    assert outcome.returncode != 0 and previewed["code"] == "kernel_execution_failed"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))
