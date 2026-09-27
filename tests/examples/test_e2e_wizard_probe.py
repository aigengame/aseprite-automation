"""Prove reusable component geometry through installed SPA and real Aseprite."""

import os
from pathlib import Path

import pytest
from PIL import Image

from examples.wizard_cast.probe import build_probe

pytestmark = pytest.mark.e2e


def test_component_pulse_preserves_other_frames_and_local_anchor(
    tmp_path: Path,
) -> None:
    cli = os.environ.get("SPA_TEST_INSTALLED_CLI", str(Path(".venv/bin/spa").resolve()))
    evidence = build_probe(cli, os.environ["SPA_TEST_ASEPRITE"], tmp_path / "probe")
    images = []
    for filename in evidence["frames"]:
        with Image.open(filename) as image:
            images.append(image.convert("RGBA"))
    assert [image.size for image in images] == [(11, 11)] * 3
    assert images[0].getbbox() == (3, 3, 8, 8)
    assert images[1].getbbox() == (2, 2, 9, 9)
    assert images[2].getbbox() is None
    assert {images[0].getpixel((x, y)) for y in range(11) for x in range(11)} <= {
        (0, 0, 0, 0),
        (111, 235, 255, 255),
    }
    assert evidence["source_positions"] == [[5, 5], [8, 6], [11, 5]]
