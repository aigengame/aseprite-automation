"""Installed Sprite geometry operations against real Aseprite."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from jsonschema import validate
from PIL import Image

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e


def _fixture(tmp_path: Path, name: str = "geometry_sprite.lua") -> Path:
    source = tmp_path / "source.aseprite"
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    with tempfile.TemporaryDirectory(prefix="spa-geometry-fixture-") as work:
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
                "--script",
                str(Path(__file__).parent / "fixtures" / name),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, process_diagnostics(run)
    return source


def _run(
    operation: str, request: dict[str, object]
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    run = spa("sprite", operation, "--input-json", json.dumps(request))
    return run, json.loads(run.stdout)


def _pixels(sprite: Path, output: Path, frame_number: int) -> Image.Image:
    run = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(sprite),
                "destination": {"path": str(output), "if_exists": "fail"},
                "frame_number": frame_number,
                "color_mode": "preserve",
                "color_profile": "preserve",
                "transparency": "preserve",
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    with Image.open(output) as image:
        return image.convert("RGBA")


def test_resize_uses_fixed_nearest_neighbor_and_reports_persisted_geometry(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path)
    target = tmp_path / "resized.aseprite"
    run, result = _run(
        "resize",
        {
            "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "width": 8,
            "height": 8,
        },
    )
    assert run.returncode == 0, run.stdout
    validate(
        result, json.loads(spa("sprite", "resize", "--schema").stdout)["result_schema"]
    )
    assert result["sampling"] == "nearest_neighbor"
    assert result["coordinate_space"] == "canvas-pixel"
    assert result["origin"] == {"x": 0, "y": 0}
    assert result["old_canvas"] == {"width": 4, "height": 4}
    assert result["new_canvas"] == {"width": 8, "height": 8}
    assert result["sprite"]["cels"][0]["bounds"] == {
        "x": 2,
        "y": 2,
        "width": 4,
        "height": 4,
    }
    assert result["sprite"]["tags"][0]["name"] == "loop"
    assert result["sprite"]["slices"][0]["keys"][0]["bounds"] == {
        "x": 2,
        "y": 2,
        "width": 4,
        "height": 4,
    }
    assert result["sprite"]["metadata"]["grid_bounds"] == {
        "x": 1,
        "y": 1,
        "width": 2,
        "height": 2,
    }
    assert result["sprite"]["cels"][1]["bounds"] == {
        "x": -2,
        "y": 4,
        "width": 6,
        "height": 4,
    }
    assert result["persisted_reopen_verified"] is True
    assert target.is_file()
    pixels = _pixels(target, tmp_path / "resized.png", 1)
    assert pixels.size == (8, 8)
    assert pixels.getpixel((2, 2)) == (255, 0, 0, 255)
    assert pixels.getpixel((3, 3)) == (255, 0, 0, 255)
    assert pixels.getpixel((4, 4)) == (0, 0, 255, 255)
    assert pixels.getpixel((1, 1))[3] == 0


def test_crop_clips_content_to_explicit_half_open_canvas_rectangle(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path)
    target = tmp_path / "cropped.aseprite"
    run, result = _run(
        "crop",
        {
            "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "coordinate_space": "canvas-pixel",
            "rectangle": {"x": 1, "y": 1, "width": 2, "height": 2},
        },
    )
    assert run.returncode == 0, run.stdout
    validate(
        result, json.loads(spa("sprite", "crop", "--schema").stdout)["result_schema"]
    )
    assert result["old_canvas"] == {"width": 4, "height": 4}
    assert result["new_canvas"] == {"width": 2, "height": 2}
    assert result["rectangle"] == {"x": 1, "y": 1, "width": 2, "height": 2}
    assert result["sprite"]["cels"][0]["bounds"] == {
        "x": 0,
        "y": 0,
        "width": 2,
        "height": 2,
    }
    assert result["clipped_cels"] == [
        {
            "layer_path": [1],
            "frame_number": 2,
            "before_bounds": {"x": -1, "y": 2, "width": 3, "height": 2},
            "retained_canvas_bounds": {"x": 1, "y": 2, "width": 1, "height": 1},
            "after_bounds": {"x": 0, "y": 1, "width": 1, "height": 1},
        }
    ]
    assert result["sprite"]["tags"][0]["name"] == "loop"
    assert result["sprite"]["slices"][0]["keys"][0]["bounds"] == {
        "x": 0,
        "y": 0,
        "width": 2,
        "height": 2,
    }
    assert result["sprite"]["metadata"]["grid_bounds"] == {
        "x": 1,
        "y": 1,
        "width": 2,
        "height": 2,
    }
    assert result["persisted_reopen_verified"] is True
    assert target.is_file()
    pixels = _pixels(target, tmp_path / "cropped.png", 2)
    assert pixels.size == (2, 2)
    assert pixels.getpixel((0, 1)) == (0, 255, 0, 255)
    assert pixels.getpixel((1, 1))[3] == 0


@pytest.mark.parametrize("operation", ["resize", "crop"])
@pytest.mark.parametrize("fixture", ["populated_sprite.lua", "tilemap_sprite.lua"])
def test_geometry_rejects_tilesets_and_tilemap_content_before_mutation(
    tmp_path: Path, operation: str, fixture: str
) -> None:
    source = _fixture(tmp_path, fixture)
    original = source.read_bytes()
    target = tmp_path / "rejected.aseprite"
    geometry = (
        {"width": 8, "height": 8}
        if operation == "resize"
        else {
            "coordinate_space": "canvas-pixel",
            "rectangle": {"x": 0, "y": 0, "width": 2, "height": 2},
        }
    )
    run, failure = _run(
        operation,
        {
            "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            **geometry,
        },
    )
    assert run.returncode == 2, run.stdout
    validate(
        failure,
        json.loads(spa("sprite", operation, "--schema").stdout)["failure_schema"],
    )
    assert failure["code"] == "sprite_geometry_unsupported_content"
    assert failure["details"]["tileset_count"] > 0
    if fixture == "tilemap_sprite.lua":
        assert failure["details"]["tilemap_layer_count"] > 0
        assert failure["details"]["tilemap_cel_count"] > 0
        assert failure["details"]["tilemap_image_count"] > 0
    assert "target_commit" not in failure
    assert not target.exists()
    assert source.read_bytes() == original


def test_crop_refuses_rectangle_outside_current_canvas(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    target = tmp_path / "rejected.aseprite"
    run, failure = _run(
        "crop",
        {
            "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "coordinate_space": "canvas-pixel",
            "rectangle": {"x": 3, "y": 1, "width": 2, "height": 2},
        },
    )
    assert run.returncode == 2, run.stdout
    assert failure["code"] == "sprite_crop_out_of_bounds"
    assert failure["details"]["canvas"] == {"width": 4, "height": 4}
    assert not target.exists()


def test_crop_reports_transparent_cel_removed_by_native_trimming(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "transparent_geometry_sprite.lua")
    target = tmp_path / "transparent-crop.aseprite"
    run, result = _run(
        "crop",
        {
            "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "coordinate_space": "canvas-pixel",
            "rectangle": {"x": 0, "y": 0, "width": 2, "height": 2},
        },
    )
    assert run.returncode == 0, run.stdout
    assert result["before_sprite"]["metadata"]["cel_count"] == 1
    assert result["sprite"]["metadata"]["cel_count"] == 0
    assert result["clipped_cels"] == [
        {
            "layer_path": [1],
            "frame_number": 1,
            "before_bounds": {"x": 1, "y": 1, "width": 2, "height": 2},
            "retained_canvas_bounds": {"x": 1, "y": 1, "width": 1, "height": 1},
            "after_bounds": None,
        }
    ]
    assert target.is_file()


def test_crop_keeps_reference_image_content_while_moving_its_cel(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "reference_geometry_sprite.lua")
    target = tmp_path / "reference-crop.aseprite"
    run, result = _run(
        "crop",
        {
            "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "coordinate_space": "canvas-pixel",
            "rectangle": {"x": 1, "y": 1, "width": 2, "height": 2},
        },
    )
    assert run.returncode == 0, run.stdout
    assert result["before_sprite"]["cels"][0]["bounds"] == {
        "x": 0,
        "y": 0,
        "width": 3,
        "height": 3,
    }
    assert result["sprite"]["cels"][0]["bounds"] == {
        "x": -1,
        "y": -1,
        "width": 3,
        "height": 3,
    }
    assert all(cel["layer_path"] != [1] for cel in result["clipped_cels"])
