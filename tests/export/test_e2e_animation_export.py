"""Native animation delivery through the public CLI and independent decoders."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from tests.export.test_e2e_export_image import _source
from tests.support import spa

pytestmark = pytest.mark.e2e


def test_sequence_keeps_order_repeated_occurrences_and_full_canvas(tmp_path: Path):
    source = _source(tmp_path)
    original = source.read_bytes()
    output = tmp_path / "sequence"
    output.mkdir()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": [2, 1, 2]},
        "layer_composition": {"mode": "visible"},
        "destination": {
            "directory": str(output),
            "filename_format": "wizard_{frame0000}.png",
            "if_exists": "fail",
        },
    }
    run = spa("export", "sequence", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert [
        item["source_frame_number"] for item in result["playback"]["occurrences"]
    ] == [2, 1, 2]
    assert [Path(item["path"]).name for item in result["artifacts"]] == [
        "wizard_0000.png",
        "wizard_0001.png",
        "wizard_0002.png",
    ]
    assert {item.name for item in output.iterdir()} == {
        "wizard_0000.png",
        "wizard_0001.png",
        "wizard_0002.png",
    }
    for ordinal, frame in enumerate([2, 1, 2]):
        with Image.open(output / f"wizard_{ordinal:04}.png") as image:
            assert image.size == (3, 2)
            rgba = image.convert("RGBA")
            expected = (17, 34, 51, 128) if frame == 2 else (200, 10, 20, 255)
            assert rgba.getpixel((1 if frame == 2 else 0, 0)) == expected
    assert source.read_bytes() == original
