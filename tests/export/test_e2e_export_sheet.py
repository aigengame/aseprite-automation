"""Sprite Sheets through the public CLI and independent file decoders."""

import hashlib
import json
import os
from pathlib import Path

import pytest
from jsonschema import validate
from PIL import Image

from tests.export.support import source_sprite
from tests.support import spa

pytestmark = pytest.mark.e2e


def sheet_request(source: Path, folder: Path) -> dict:
    return {
        "source_sprite_file": str(source),
        "image_destination": {"path": str(folder / "sheet.png"), "if_exists": "fail"},
        "metadata_destination": {
            "path": str(folder / "sheet.json"),
            "if_exists": "fail",
        },
        "selection": {"kind": "range", "from_frame": 1, "to_frame": 2},
        "layer_composition": {"mode": "visible"},
        "output_color_mode": "rgb",
        "layout": {"kind": "horizontal"},
        "trim": "none",
        "padding": {"border": 0, "shape": 0, "inner": 0},
        "filename_format": "wizard_{frame0001}",
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }


def test_sheet_publishes_two_verified_artifacts_without_changing_source(
    tmp_path: Path,
) -> None:
    source = source_sprite(tmp_path)
    before = source.read_bytes()
    request = sheet_request(source, tmp_path)

    run = spa("export", "sheet", "--input-json", json.dumps(request))

    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    validate(
        result, json.loads(spa("export", "sheet", "--schema").stdout)["result_schema"]
    )
    assert result["source_frames"] == [1, 2]
    assert result["width"] == 6 and result["height"] == 2
    metadata = json.loads((tmp_path / "sheet.json").read_text())
    assert [f["filename"] for f in metadata["frames"]] == ["wizard_0001", "wizard_0002"]
    assert [f["duration"] for f in metadata["frames"]] == [100, 100]
    assert metadata["meta"]["image"] == "sheet.png"
    with Image.open(tmp_path / "sheet.png") as image:
        assert image.size == (6, 2)
        rgba = image.convert("RGBA")
        assert rgba.getpixel((0, 0)) == (200, 10, 20, 255)
        assert rgba.getpixel((4, 0)) == (17, 34, 51, 128)
    for artifact, role, suffix in zip(
        result["artifacts"], ("image", "metadata"), ("png", "json"), strict=True
    ):
        path = tmp_path / f"sheet.{suffix}"
        assert artifact["role"] == role and artifact["path"] == str(path)
        assert artifact["byte_size"] == len(path.read_bytes())
        assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert source.read_bytes() == before
