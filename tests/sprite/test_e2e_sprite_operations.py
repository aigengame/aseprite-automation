"""Copy, flatten, and validation through the installed Sprite commands."""

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
from tests.support import spa

pytestmark = pytest.mark.e2e


def _create(tmp_path: Path) -> Path:
    source = tmp_path / "source.aseprite"
    run = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "target_sprite_file": str(source),
                "width": 3,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {"kind": "transparent"},
                "overwrite": False,
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    return source


def _fixture(tmp_path: Path, name: str, **params: str) -> Path:
    source = tmp_path / "source.aseprite"
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    with tempfile.TemporaryDirectory(prefix="spa-sprite-fixture-") as work:
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
                    for key, value in params.items()
                    for argument in ("--script-param", f"{key}={value}")
                ],
                "--script",
                str(Path(__file__).parent / "fixtures" / name),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr
    assert source.is_file()
    return source


def _export_pixels(sprite_file: Path, destination: Path, frame_number: int) -> bytes:
    run = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(sprite_file),
                "destination": {"path": str(destination), "if_exists": "fail"},
                "frame_number": frame_number,
                "color_mode": "preserve",
                "color_profile": "preserve",
                "transparency": "preserve",
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    with Image.open(destination) as image:
        image.load()
        return image.convert("RGBA").tobytes()


def test_validate_reports_only_declared_checks_and_mismatches(tmp_path: Path) -> None:
    source = _create(tmp_path)
    run = spa(
        "sprite",
        "validate",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(source),
                "expected": {
                    "width": 3,
                    "height": 4,
                    "color_mode": "rgb",
                    "frame_count": 1,
                },
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
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


def test_copy_preserves_tile_bearing_native_bytes_and_reopens(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "tilemap_sprite.lua")
    target = tmp_path / "copied.aseprite"
    run = spa(
        "sprite",
        "copy",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": False,
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(
        result, json.loads(spa("sprite", "copy", "--schema").stdout)["result_schema"]
    )
    assert result["persisted_reopen_verified"] is True
    assert result["sprite"]["metadata"]["tileset_count"] > 0
    assert any(layer["is_tilemap"] for layer in result["sprite"]["layers"])
    assert target.read_bytes() == source.read_bytes()
    reopened = spa(
        "sprite",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(target),
                "inspection_scope": ["layers", "tilesets"],
            }
        ),
    )
    assert reopened.returncode == 0, reopened.stdout
    assert json.loads(reopened.stdout)["metadata"]["tileset_count"] > 0


def test_copy_requires_a_distinct_target_and_overwrite_permission(
    tmp_path: Path,
) -> None:
    source = _create(tmp_path)
    original = source.read_bytes()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(source),
        "overwrite": True,
    }
    same_target = spa("sprite", "copy", "--input-json", json.dumps(request))
    assert same_target.returncode != 0
    same_failure = json.loads(same_target.stdout)
    assert same_failure["code"] == "invalid_request"
    assert same_failure["details"]["errors"][0]["location"] == ["target_sprite_file"]
    assert source.read_bytes() == original

    target = tmp_path / "existing.aseprite"
    target.write_bytes(b"existing")
    request.update(target_sprite_file=str(target), overwrite=False)
    refused = spa("sprite", "copy", "--input-json", json.dumps(request))
    assert refused.returncode != 0
    assert json.loads(refused.stdout)["code"] == "target_commit_failed"
    assert target.read_bytes() == b"existing"
    assert source.read_bytes() == original
    assert not list(tmp_path.glob("*.staged.aseprite"))


def test_copy_reports_source_staging_failure_without_target_commit(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.aseprite"
    target = tmp_path / "copy.aseprite"
    run = spa(
        "sprite",
        "copy",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(missing),
                "target_sprite_file": str(target),
                "overwrite": False,
            }
        ),
    )
    assert run.returncode != 0
    failure = json.loads(run.stdout)
    validate(
        failure, json.loads(spa("sprite", "copy", "--schema").stdout)["failure_schema"]
    )
    assert failure["code"] == "sprite_copy_staging_failed"
    assert failure["details"] == {
        "kind": "sprite_copy_staging",
        "source_sprite_file": str(missing),
        "target_sprite_file": str(target),
    }
    assert not target.exists()
    assert not list(tmp_path.glob("*.staged.aseprite"))


def test_flatten_reports_all_structural_consequences_after_reopen(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "flatten_sprite.lua")
    original = source.read_bytes()
    target = tmp_path / "flattened.aseprite"
    run = spa(
        "sprite",
        "flatten",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": False,
                "overwrite": False,
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
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
        assert _export_pixels(
            source, tmp_path / f"before-{frame_number}.png", frame_number
        ) == _export_pixels(
            target, tmp_path / f"after-{frame_number}.png", frame_number
        )


def test_flatten_in_place_requires_explicit_intent(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "flatten_sprite.lua")
    original = source.read_bytes()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(source),
        "in_place": False,
        "overwrite": True,
    }
    refused = spa("sprite", "flatten", "--input-json", json.dumps(request))
    assert refused.returncode != 0
    assert json.loads(refused.stdout)["code"] == "invalid_request"
    assert source.read_bytes() == original

    request["in_place"] = True
    run = spa("sprite", "flatten", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["target_commit"]["target_sprite_file"] == str(source)
    assert result["sprite"]["metadata"]["layer_count"] == 1
    assert source.read_bytes() != original


def test_flatten_reports_indexed_palette_and_color_mode(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "flatten_sprite.lua", mode="indexed")
    target = tmp_path / "indexed-flat.aseprite"
    run = spa(
        "sprite",
        "flatten",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": False,
                "overwrite": False,
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["before_sprite"]["metadata"]["color_mode"] == "indexed"
    assert result["sprite"]["metadata"]["color_mode"] == "indexed"
    assert result["sprite"]["palettes"] == result["before_sprite"]["palettes"]
    assert result["sprite"]["metadata"]["layer_count"] == 1


def test_flatten_includes_hidden_layer_pixels_in_native_result(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "hidden_layer_sprite.lua")
    target = tmp_path / "hidden-flat.aseprite"
    before_pixel = _export_pixels(source, tmp_path / "hidden-before.png", 1)
    assert before_pixel[:4] == bytes((0, 0, 255, 255))
    run = spa(
        "sprite",
        "flatten",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": False,
                "overwrite": False,
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["before_sprite"]["layers"][1]["is_visible"] is False
    assert result["sprite"]["metadata"]["layer_count"] == 1
    after_pixel = _export_pixels(target, tmp_path / "hidden-after.png", 1)
    assert after_pixel[:4] == bytes((255, 0, 0, 255))


@pytest.mark.parametrize(
    ("fixture", "tilemaps"),
    [("populated_sprite.lua", 0), ("tilemap_sprite.lua", 1)],
)
def test_flatten_rejects_tile_content_before_target_commit(
    tmp_path: Path, fixture: str, tilemaps: int
) -> None:
    source = _fixture(tmp_path, fixture)
    original = source.read_bytes()
    target = tmp_path / "unsupported.aseprite"
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
    }
    run = spa("sprite", "flatten", "--input-json", json.dumps(request))
    assert run.returncode != 0
    failure = json.loads(run.stdout)
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
