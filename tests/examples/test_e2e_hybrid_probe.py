"""Generated raster input reaches saved Cels and PNGs through installed SPA."""

import os
from pathlib import Path

import pytest

from examples.wizard_cast_v2.probe import build_probe

pytestmark = pytest.mark.e2e


def test_generated_pose_pixel_handoff_and_independent_placement(tmp_path: Path) -> None:
    executable = os.environ.get(
        "SPA_TEST_INSTALLED_CLI", str(Path(".venv/bin/spa").resolve())
    )
    result = build_probe(
        executable, os.environ["SPA_TEST_ASEPRITE"], tmp_path / "probe"
    )
    assert result["pixel_correspondence"]
    cels = result["reopened"]["cels"]
    assert [{"x": cel["bounds"]["x"], "y": cel["bounds"]["y"]} for cel in cels] == [
        {"x": 0, "y": 0},
        {"x": 2, "y": 1},
        {"x": 0, "y": 0},
    ]
    assert [cel["opacity"] for cel in cels] == [255, 255, 0]
    assert result["reopened"]["metadata"]["frame_count"] == 3
