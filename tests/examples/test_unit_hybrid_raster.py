"""Frozen generated input must meet the declared asset contract before authoring."""

from pathlib import Path

import pytest
from PIL import Image

from examples.wizard_cast_v2.raster import read_pixels


def test_raster_translation_preserves_coordinates_and_ignores_transparent_rgb(
    tmp_path: Path,
) -> None:
    path = tmp_path / "input.png"
    image = Image.new("RGBA", (3, 2), (91, 13, 7, 0))
    image.putpixel((2, 1), (101, 214, 209, 255))
    image.save(path)
    assert read_pixels(path, {"magic": "#65d6d1"}) == (3, 2, {(2, 1): "magic"})


@pytest.mark.parametrize(
    "pixel,reason",
    [((101, 214, 209, 127), "nonbinary alpha"), ((255, 0, 0, 255), "undeclared color")],
)
def test_raster_translation_rejects_unprepared_inputs(
    tmp_path: Path, pixel: tuple, reason: str
) -> None:
    path = tmp_path / "invalid.png"
    Image.new("RGBA", (1, 1), pixel).save(path)
    with pytest.raises(ValueError, match=reason):
        read_pixels(path, {"magic": "#65d6d1"})
