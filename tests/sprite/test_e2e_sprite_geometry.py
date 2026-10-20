"""Installed Sprite geometry operations against real Aseprite."""

import json
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, render_frame, run, run_lua
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"


def _geometry_sprite(runtime: RuntimeObservation, target: Path) -> None:
    """Write the Sprite of `geometry_sprite.lua` to target."""
    lua = run_lua(FIXTURES / "geometry_sprite.lua", runtime, out=target)
    assert lua.returncode == 0, process_diagnostics(lua)


def test_resize_uses_fixed_nearest_neighbor_and_reports_persisted_geometry(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    _geometry_sprite(runtime, source)
    target = tmp_path / "resized.aseprite"
    result = expect_success(
        "sprite resize",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "width": 8,
            "height": 8,
        },
    )
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
    pixels = render_frame(target, 1)
    assert pixels.size == (8, 8)
    assert pixels.getpixel((2, 2)) == (255, 0, 0, 255)
    assert pixels.getpixel((3, 3)) == (255, 0, 0, 255)
    assert pixels.getpixel((4, 4)) == (0, 0, 255, 255)
    assert pixels.getpixel((1, 1))[3] == 0


def test_crop_clips_content_to_explicit_half_open_canvas_rectangle(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    _geometry_sprite(runtime, source)
    target = tmp_path / "cropped.aseprite"
    result = expect_success(
        "sprite crop",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "coordinate_space": "canvas-pixel",
            "rectangle": {"x": 1, "y": 1, "width": 2, "height": 2},
        },
    )
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
    pixels = render_frame(target, 2)
    assert pixels.size == (2, 2)
    assert pixels.getpixel((0, 1)) == (0, 255, 0, 255)
    assert pixels.getpixel((1, 1))[3] == 0


@pytest.mark.parametrize("operation", ["resize", "crop"])
@pytest.mark.parametrize("fixture", ["populated_sprite.lua", "tilemap_sprite.lua"])
def test_geometry_rejects_tilesets_and_tilemap_content_before_mutation(
    runtime: RuntimeObservation, tmp_path: Path, operation: str, fixture: str
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / fixture, runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
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
    outcome = run(
        f"sprite {operation}",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            **geometry,
        },
    )
    failure = outcome.envelope
    assert outcome.returncode == 2, failure
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


def test_crop_refuses_rectangle_outside_current_canvas(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    _geometry_sprite(runtime, source)
    target = tmp_path / "rejected.aseprite"
    outcome = run(
        "sprite crop",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "coordinate_space": "canvas-pixel",
            "rectangle": {"x": 3, "y": 1, "width": 2, "height": 2},
        },
    )
    failure = outcome.envelope
    assert outcome.returncode == 2, failure
    assert failure["code"] == "sprite_crop_out_of_bounds"
    assert failure["details"]["canvas"] == {"width": 4, "height": 4}
    assert not target.exists()


def test_crop_reports_transparent_cel_removed_by_native_trimming(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "transparent_geometry_sprite.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    target = tmp_path / "transparent-crop.aseprite"
    result = expect_success(
        "sprite crop",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "coordinate_space": "canvas-pixel",
            "rectangle": {"x": 0, "y": 0, "width": 2, "height": 2},
        },
    )
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
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "reference_geometry_sprite.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    target = tmp_path / "reference-crop.aseprite"
    result = expect_success(
        "sprite crop",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "coordinate_space": "canvas-pixel",
            "rectangle": {"x": 1, "y": 1, "width": 2, "height": 2},
        },
    )
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
