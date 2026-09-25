"""Installed animation audit, compare, and preview against native Aseprite."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _source(tmp_path: Path, fixture: str, **params: str) -> Path:
    source = tmp_path / "source.aseprite"
    binary = Path(os.environ["SPA_TEST_ASEPRITE"])
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    fixture_path = Path(__file__).parent / "fixtures" / fixture
    if fixture in {"rgb_frames.lua", "rgb_profile_alpha.lua", "rgb_tilemap.lua"}:
        fixture_path = Path(__file__).parents[1] / "export" / "fixtures" / fixture
    with tempfile.TemporaryDirectory(prefix="spa-animation-fixture-") as work:
        prepared = prepare_invocation(binary, resource, Path(work))
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
                str(fixture_path),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr
    return source


def _run(command: str, request: dict[str, object]) -> tuple[int, dict]:
    run = spa(
        "animation",
        command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)


def test_audit_reports_exact_declared_coverage_and_findings(tmp_path: Path) -> None:
    source = _source(tmp_path, "coverage.lua")
    code, result = _run(
        "audit",
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
    assert code == 0, result
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


def test_audit_allows_undeclared_absent_cel(tmp_path: Path) -> None:
    source = _source(tmp_path, "coverage.lua")
    code, result = _run(
        "audit",
        {
            "sprite_file": str(source),
            "from_frame": 1,
            "to_frame": 3,
            "required_cels": [],
            "non_overlap": [],
        },
    )
    assert code == 0, result
    assert result["complete"] is True
    assert result["required_cels"] == []
    assert result["durations"] == []
    assert result["overlaps"] == []
    assert result["findings"] == []


def test_audit_uses_quantized_native_effective_alpha(tmp_path: Path) -> None:
    source = _source(tmp_path, "low_opacity.lua")
    code, result = _run(
        "audit",
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
    assert code == 0, result
    assert result["overlaps"][0]["overlap_pixels"] == 0
    assert result["findings"] == []


def test_audit_ignores_hidden_cel_in_declared_pair(tmp_path: Path) -> None:
    source = _source(tmp_path, "rgb_frames.lua")
    code, result = _run(
        "audit",
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
    assert code == 0, result
    assert result["overlaps"][0]["overlap_pixels"] == 0
    assert result["findings"] == []


def test_audit_reports_typed_coverage_limit_before_inspection(tmp_path: Path) -> None:
    source = _source(tmp_path, "coverage.lua")
    code, failure = _run(
        "audit",
        {
            "sprite_file": str(source),
            "from_frame": 1,
            "to_frame": 1,
            "required_cels": [
                {"layer": {"layer_path": [1]}, "frame_number": 1} for _ in range(1025)
            ],
        },
    )
    assert code != 0 and failure["code"] == "audit_limit_exceeded"
    assert failure["details"] == {
        "kind": "operation_limit",
        "unit": "coverage_observations",
        "requested": 1025,
        "allowed_minimum": 0,
        "allowed_maximum": 1024,
    }


def test_audit_reports_typed_overlap_pixel_limit(tmp_path: Path) -> None:
    source = _source(tmp_path, "coverage.lua", width="1024", height="1024")
    pair = {
        "first_layer": {"layer_path": [1]},
        "second_layer": {"layer_path": [2]},
    }
    code, failure = _run(
        "audit",
        {
            "sprite_file": str(source),
            "from_frame": 1,
            "to_frame": 3,
            "non_overlap": [pair] * 6,
        },
    )
    assert code != 0 and failure["code"] == "audit_limit_exceeded"
    assert failure["details"] == {
        "kind": "operation_limit",
        "unit": "overlap_pixel_checks",
        "requested": 18_874_368,
        "allowed_minimum": 0,
        "allowed_maximum": 16_777_216,
    }


def test_compare_counts_full_canvas_rgba_differences(tmp_path: Path) -> None:
    source = _source(tmp_path, "rgb_frames.lua")
    request = {"sprite_file": str(source), "earlier_frame": 1, "later_frame": 2}
    code, different = _run("compare", request)
    assert code == 0, different
    assert different["complete"] is True
    assert different["color_mode"] == "rgb"
    assert different["bounds"] == {"x": 0, "y": 0, "width": 3, "height": 2}
    assert different["differing_pixels"] == 2
    identical_source = _source(
        tmp_path,
        "rgb_profile_alpha.lua",
        profile="none",
        alpha="opaque",
        two_frames="true",
    )
    code, same = _run("compare", {**request, "sprite_file": str(identical_source)})
    assert code == 0, same
    assert same["differing_pixels"] == 0


def test_preview_publishes_verified_overlay_without_source_mutation(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path, "rgb_frames.lua")
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "preview.png"
    request = {
        "source_sprite_file": str(source),
        "earlier_frame": 1,
        "later_frame": 2,
        "destination": {"path": str(destination), "if_exists": "fail"},
    }
    code, result = _run("preview", request)
    assert code == 0, result
    assert result["destination"] == request["destination"]
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


def test_preview_requires_explicit_replacement_intent(tmp_path: Path) -> None:
    source = _source(tmp_path, "rgb_frames.lua")
    destination = tmp_path / "preview.png"
    destination.write_bytes(b"existing")
    request = {
        "source_sprite_file": str(source),
        "earlier_frame": 1,
        "later_frame": 2,
        "destination": {"path": str(destination), "if_exists": "fail"},
    }
    code, failure = _run("preview", request)
    assert code != 0 and failure["code"] == "artifact_file_failed"
    assert destination.read_bytes() == b"existing"
    code, result = _run(
        "preview",
        {**request, "destination": {"path": str(destination), "if_exists": "replace"}},
    )
    assert code == 0, result
    assert destination.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_preview_rejects_destination_traversed_by_source_alias(tmp_path: Path) -> None:
    native_source = _source(tmp_path, "rgb_frames.lua")
    destination = tmp_path / "preview.png"
    shutil.copyfile(native_source, destination)
    source = tmp_path / "linked.aseprite"
    source.symlink_to(destination)
    original = hashlib.sha256(source.read_bytes()).hexdigest()

    code, failure = _run(
        "preview",
        {
            "source_sprite_file": str(source),
            "earlier_frame": 1,
            "later_frame": 2,
            "destination": {"path": str(destination), "if_exists": "replace"},
        },
    )

    assert code != 0 and failure["code"] == "artifact_file_failed"
    assert failure["details"]["reason"] == "source_destination_alias"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == original


def test_preview_reports_unverifiable_source_destination_identity(
    tmp_path: Path,
) -> None:
    native_source = _source(tmp_path, "rgb_frames.lua")
    private = tmp_path / "private"
    private.mkdir()
    source = private / "source.aseprite"
    shutil.copyfile(native_source, source)
    destination = private / "preview.png"
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
            "animation",
            "preview",
            "--input-json",
            json.dumps(
                {
                    "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                    "source_sprite_file": str(source),
                    "earlier_frame": 1,
                    "later_frame": 2,
                    "destination": {"path": str(destination), "if_exists": "replace"},
                }
            ),
        )
    finally:
        private.chmod(0o700)

    assert run.returncode != 0 and run.stdout
    failure = json.loads(run.stdout)
    assert failure["code"] == "artifact_file_failed"
    assert failure["details"]["reason"] == "source_destination_identity_unverified"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == original


@pytest.mark.parametrize("alpha", ["opaque", "partial", "transparent"])
def test_preview_decoded_alpha_fixtures(tmp_path: Path, alpha: str) -> None:
    source = _source(
        tmp_path,
        "rgb_profile_alpha.lua",
        profile="none",
        alpha=alpha,
        two_frames="true",
    )
    destination = tmp_path / "preview.png"
    code, result = _run(
        "preview",
        {
            "source_sprite_file": str(source),
            "earlier_frame": 1,
            "later_frame": 2,
            "destination": {"path": str(destination), "if_exists": "fail"},
        },
    )
    assert code == 0, result
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
    tmp_path: Path, fixture: str, params: dict[str, str]
) -> None:
    source = _source(tmp_path, fixture, two_frames="true", **params)
    destination = tmp_path / "preview.png"
    code, compared = _run(
        "compare", {"sprite_file": str(source), "earlier_frame": 1, "later_frame": 2}
    )
    assert code != 0 and compared["code"] == "kernel_execution_failed"
    code, previewed = _run(
        "preview",
        {
            "source_sprite_file": str(source),
            "earlier_frame": 1,
            "later_frame": 2,
            "destination": {"path": str(destination), "if_exists": "fail"},
        },
    )
    assert code != 0 and previewed["code"] == "kernel_execution_failed"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.staged.png"))
