"""Translate frozen example rasters into the existing public Pixel Patch input."""

from pathlib import Path

from PIL import Image


def read_pixels(path: Path, palette: dict[str, str]) -> tuple[int, int, dict]:
    """Reject contract violations before the first native mutation."""
    names = {value.lower(): name for name, value in palette.items()}
    with Image.open(path) as source:
        image = source.convert("RGBA")
    pixels = {}
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = image.getpixel((x, y))
            if alpha not in (0, 255):
                raise ValueError(f"{path.name}: nonbinary alpha at {(x, y)}")
            if not alpha:
                continue
            color = f"#{red:02x}{green:02x}{blue:02x}"
            if color not in names:
                raise ValueError(f"{path.name}: undeclared color {color} at {(x, y)}")
            pixels[x, y] = names[color]
    return image.width, image.height, pixels
