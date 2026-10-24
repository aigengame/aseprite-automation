"""Copy, flatten, and validation through the installed Sprite commands."""

import json
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, render_frame, run, run_lua
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"


def _create(tmp_path: Path) -> Path:
    """Create a 3x2 RGB Sprite with one transparent Layer, and return its path."""
    source = tmp_path / "source.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    return source


def test_validate_reports_only_declared_checks_and_mismatches(tmp_path: Path) -> None:
    source = _create(tmp_path)
    result = expect_success(
        "sprite validate",
        {
            "sprite_file": str(source),
            "expected": {
                "width": 3,
                "height": 4,
                "color_mode": "rgb",
                "frame_count": 1,
            },
        },
    )
    validate(
        result,
        json.loads(spa("sprite", "validate", "--schema").stdout)["result_schema"],
    )
    assert result["operation"] == "spa sprite validate"
    assert result["status"] == "success"
    assert result["valid"] is False
    assert result["checks"] == [
        {"fact": "width", "expected": 3, "actual": 3, "matches": True},
        {"fact": "height", "expected": 4, "actual": 2, "matches": False},
        {"fact": "color_mode", "expected": "rgb", "actual": "rgb", "matches": True},
        {"fact": "frame_count", "expected": 1, "actual": 1, "matches": True},
    ]
    assert result["findings"] == [
        {
            "kind": "sprite_fact_mismatch",
            "subject": "sprite",
            "fact": "height",
            "expected": 4,
            "actual": 2,
        }
    ]


def test_copy_preserves_tile_bearing_native_bytes_and_reopens(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "tilemap_sprite.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    target = tmp_path / "copied.aseprite"
    result = expect_success(
        "sprite copy",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "overwrite": False,
        },
    )
    validate(
        result, json.loads(spa("sprite", "copy", "--schema").stdout)["result_schema"]
    )
    assert result["persisted_reopen_verified"] is True
    assert result["sprite"]["metadata"]["tileset_count"] > 0
    assert any(layer["is_tilemap"] for layer in result["sprite"]["layers"])
    assert target.read_bytes() == source.read_bytes()
    reopened = expect_success(
        "sprite get",
        {
            "sprite_file": str(target),
            "inspection_scope": ["layers", "tilesets"],
        },
    )
    assert reopened["metadata"]["tileset_count"] > 0


def test_copy_refuses_an_existing_target_without_overwrite(tmp_path: Path) -> None:
    source = _create(tmp_path)
    original = source.read_bytes()
    target = tmp_path / "existing.aseprite"
    target.write_bytes(b"existing")
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "overwrite": False,
    }
    refused = run("sprite copy", request)
    assert refused.returncode != 0, refused.envelope
    assert refused.envelope["code"] == "target_commit_failed"
    assert target.read_bytes() == b"existing"
    assert source.read_bytes() == original
    assert not list(tmp_path.glob("*.staged.aseprite"))


def test_flatten_reports_all_structural_consequences_after_reopen(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "flatten_sprite.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    original = source.read_bytes()
    target = tmp_path / "flattened.aseprite"
    result = expect_success(
        "sprite flatten",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
        },
    )
    validate(
        result,
        json.loads(spa("sprite", "flatten", "--schema").stdout)["result_schema"],
    )
    assert result["persisted_reopen_verified"] is True
    before = result["before_sprite"]
    after = result["sprite"]
    assert before["metadata"]["layer_count"] == 2
    assert after["metadata"]["layer_count"] == 1
    assert before["metadata"]["use_layer_uuids"] is True
    assert after["metadata"]["use_layer_uuids"] is True
    assert after["layers"][0]["layer_uuid"] is not None
    assert after["metadata"]["frame_count"] == 2
    assert after["metadata"]["color_mode"] == before["metadata"]["color_mode"]
    assert after["palettes"] == before["palettes"]
    assert after["tags"] == before["tags"]
    assert after["slices"] == before["slices"]
    assert len(after["cels"]) == after["metadata"]["cel_count"]
    assert after["layers"] != before["layers"]
    assert target.is_file()
    assert source.read_bytes() == original
    for frame_number in (1, 2):
        assert (
            render_frame(source, frame_number).tobytes()
            == render_frame(target, frame_number).tobytes()
        )


def test_flatten_in_place_replaces_the_source(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "flatten_sprite.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    original = source.read_bytes()
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(source),
        "in_place": True,
        "overwrite": True,
    }
    result = expect_success("sprite flatten", request)
    assert result["target_commit"]["target_sprite_file"] == str(source)
    assert result["sprite"]["metadata"]["layer_count"] == 1
    assert source.read_bytes() != original


def test_flatten_reports_indexed_palette_and_color_mode(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "flatten_sprite.lua", runtime, out=source, mode="indexed")
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    target = tmp_path / "indexed-flat.aseprite"
    result = expect_success(
        "sprite flatten",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
        },
    )
    assert result["before_sprite"]["metadata"]["color_mode"] == "indexed"
    assert result["sprite"]["metadata"]["color_mode"] == "indexed"
    assert result["sprite"]["palettes"] == result["before_sprite"]["palettes"]
    assert result["sprite"]["metadata"]["layer_count"] == 1


def test_flatten_includes_hidden_layer_pixels_in_native_result(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "hidden_layer_sprite.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    target = tmp_path / "hidden-flat.aseprite"
    before_pixel = render_frame(source, 1).tobytes()
    assert before_pixel[:4] == bytes((0, 0, 255, 255))
    result = expect_success(
        "sprite flatten",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
        },
    )
    assert result["before_sprite"]["layers"][1]["is_visible"] is False
    assert result["sprite"]["metadata"]["layer_count"] == 1
    after_pixel = render_frame(target, 1).tobytes()
    assert after_pixel[:4] == bytes((255, 0, 0, 255))


@pytest.mark.parametrize(
    ("fixture", "tilemaps"),
    [("populated_sprite.lua", 0), ("tilemap_sprite.lua", 1)],
)
def test_flatten_rejects_tile_content_before_target_commit(
    runtime: RuntimeObservation, tmp_path: Path, fixture: str, tilemaps: int
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / fixture, runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    original = source.read_bytes()
    target = tmp_path / "unsupported.aseprite"
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
    }
    outcome = run("sprite flatten", request)
    failure = outcome.envelope
    assert outcome.returncode != 0, failure
    validate(
        failure,
        json.loads(spa("sprite", "flatten", "--schema").stdout)["failure_schema"],
    )
    assert failure["code"] == "sprite_flatten_unsupported_content"
    assert failure["details"]["tileset_count"] > 0
    assert failure["details"]["tilemap_layer_count"] == tilemaps
    assert not target.exists()
    assert source.read_bytes() == original
    assert not list(tmp_path.glob("*.staged.aseprite"))
