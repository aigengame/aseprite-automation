"""Generated raster input reaches saved Cels and PNGs through installed SPA."""

import os
from pathlib import Path

import pytest

from examples.wizard_cast_v2.probe import build_probe
from tests.support import installed_cli

pytestmark = pytest.mark.e2e


def test_generated_pose_pixel_handoff_and_independent_placement(tmp_path: Path) -> None:
    executable = installed_cli()
    result = build_probe(
        executable, os.environ["SPA_TEST_ASEPRITE"], tmp_path / "probe"
    )
    # build_probe compares each exported Frame with the input placed at its Cel
    # position, and raises on a mismatch. Its "pixel_correspondence" is a literal.
    cels = result["reopened"]["cels"]
    assert [{"x": cel["bounds"]["x"], "y": cel["bounds"]["y"]} for cel in cels] == [
        {"x": 0, "y": 0},
        {"x": 2, "y": 1},
        {"x": 0, "y": 0},
    ]
    assert [cel["opacity"] for cel in cels] == [255, 255, 0]
    assert result["reopened"]["metadata"]["frame_count"] == 3
