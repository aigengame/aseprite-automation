"""Assemble frozen art and finite motion rules; SPA authors the native animation."""

import json
import math
from dataclasses import dataclass
from functools import cache
from itertools import pairwise
from pathlib import Path

from PIL import Image

from examples.wizard_cast_v2.raster import read_pixels

ROOT = Path(__file__).parent


@dataclass
class Component:
    width: int
    height: int
    pixels: dict[tuple[int, int], str]
    position: tuple[int, int] = (0, 0)
    opacity: int = 255
    local_position: tuple[int, int] = (0, 0)


def load_recipe(path: Path | None = None) -> dict:
    return json.loads((path or ROOT / "recipe.json").read_text())


def phases(recipe: dict) -> list[dict]:
    result, start = [], 0
    for phase in recipe["phases"]:
        result.append({**phase, "start": start, "end": start + phase["frames"] - 1})
        start += phase["frames"]
    return result


def total_frames(recipe: dict) -> int:
    return sum(phase["frames"] for phase in recipe["phases"])


def _round(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


@cache
def _asset(filename: str, palette_json: str) -> tuple[int, int, dict]:
    return read_pixels(ROOT / "inputs/prepared" / filename, json.loads(palette_json))


def _read(recipe: dict, name: str) -> tuple[int, int, dict]:
    return _asset(recipe["inputs"][name], json.dumps(recipe["palette"], sort_keys=True))


def _motion(recipe: dict, index: int) -> tuple[int, int]:
    if index < 4:
        return (0, -recipe["motion"]["idle_bob_pixels"] if index >= 2 else 0)
    keys = recipe["motion"]["offsets"]
    for left, right in pairwise(keys):
        if left["frame"] <= index <= right["frame"]:
            t = (index - left["frame"]) / (right["frame"] - left["frame"])
            eased = t * t * (3 - 2 * t)
            return tuple(
                _round(a + (b - a) * eased)
                for a, b in zip(left["offset"], right["offset"])
            )
    return tuple(keys[-1]["offset"])


def _place(
    width: int,
    height: int,
    pixels: dict,
    local: tuple,
    shake: tuple = (0, 0),
    opacity: int = 255,
) -> Component:
    return Component(
        width,
        height,
        pixels,
        (local[0] + shake[0], local[1] + shake[1]),
        opacity,
        local,
    )


def _resized_pixels(recipe: dict, name: str, size: tuple[int, int]) -> dict:
    """A declared asset transform, never a replacement character renderer."""
    with Image.open(ROOT / "inputs/prepared" / recipe["inputs"][name]) as source:
        image = source.convert("RGBA").resize(size, Image.Resampling.NEAREST)
    names = {value.lower(): key for key, value in recipe["palette"].items()}
    return {
        (x, y): names["#" + bytes(image.getpixel((x, y))[:3]).hex()]
        for y in range(image.height)
        for x in range(image.width)
        if image.getpixel((x, y))[3]
    }


def _sparks(recipe: dict, index: int) -> dict:
    if not 4 <= index <= 22:
        return {}
    _, _, glyph = _read(recipe, "spark")
    pixels = {}
    count = recipe["particles"]["count"]
    for number in range(count):
        if index < 14:
            age = (index - 4 + number % 4) % 10
            radius = 44 - 4 * age
            angle = number * math.tau / count - age * 0.33
        else:
            age = index - 14 - number % 3
            if not 0 <= age < 7:
                continue
            radius = 8 + age * 7
            angle = number * math.tau / count + age * 0.08
        color = recipe["particles"]["colors"][min(age // 3, 2)]
        center = (
            80 + _round(math.cos(angle) * radius),
            80 + _round(math.sin(angle) * radius),
        )
        for x, y in glyph:
            pixels[center[0] + x - 3, center[1] + y - 3] = color
    return pixels


def sample_frame(recipe: dict, index: int) -> dict[str, Component]:
    if not 0 <= index < total_frames(recipe):
        raise ValueError("Frame index outside the finite recipe")
    shake = tuple(
        next(
            (v["offset"] for v in recipe["scene"]["shake"] if v["frame"] == index),
            [0, 0],
        )
    )
    motion = _motion(recipe, index)
    pose_name = next(
        item["pose"] for item in recipe["poses"] if item["from"] <= index <= item["to"]
    )
    pose = recipe["pose_geometry"][pose_name]
    width, height, authored = _read(recipe, pose_name)
    wizard = dict(authored)
    gem_center = pose["gem"]
    # Separate the supplied gemstone from its mount. The independent generated
    # gem is then authored by SPA as a Cel, so flicker and native pulse are real.
    for coordinate, color in list(wizard.items()):
        if (
            abs(coordinate[0] - gem_center[0]) <= 7
            and abs(coordinate[1] - gem_center[1]) <= 10
            and color in ("magic", "magic_light", "white", "magic_dark")
        ):
            del wizard[coordinate]
    # Palette-only rim light follows the supplied silhouette. This finite overlay
    # neither invents anatomy nor redraws the character from primitives.
    rim_color = (
        "magic_light"
        if 11 <= index <= 16
        else "magic"
        if 4 <= index <= 22
        else "magic_dark"
    )
    for x, y in authored:
        if (
            45 < y < 130
            and x < gem_center[0] - 8
            and (x + 1, y) not in authored
            and (x, y) in wizard
        ):
            wizard[x, y] = rim_color
    position = tuple(recipe["wizard_position"][axis] + motion[axis] for axis in (0, 1))
    gem_world = tuple(position[axis] + gem_center[axis] for axis in (0, 1))
    gem_width, gem_height, gem_pixels = _read(recipe, "gem")
    gem_local = tuple(
        gem_world[axis] - recipe["gem"]["anchor"][axis] for axis in (0, 1)
    )
    gem_opacity = 0 if index in recipe["gem"]["hidden_frames"] else 255

    background_width, background_height, background = _read(recipe, "background")
    stars = {}
    for number, point in enumerate(recipe["scene"]["stars"]):
        if (index + number * 3) % 8 < 3:
            stars[tuple(point)] = "moon" if index % 8 else "white"
    effect_local = (gem_world[0] - 80, gem_world[1] - 80)
    burst = {}
    if 14 <= index <= 19:
        size = recipe["burst"]["sizes"][index - 14]
        if size:
            for (x, y), color in _resized_pixels(recipe, "burst", (size, size)).items():
                burst[x + 80 - size // 2, y + 80 - size // 2] = color

    projectile_width, projectile_height, projectile = _read(recipe, "projectile")
    if 14 <= index <= 19:
        cutoff = [0, 2, 4, 1, 3, 0][index - 14]
        projectile = {
            point: color for point, color in projectile.items() if point[0] >= cutoff
        }
    else:
        projectile = {}
    travel = recipe["projectile"]["travel"][max(0, min(index - 14, 5))]
    projectile_position = tuple(
        recipe["projectile"]["origin"][axis]
        + travel[axis]
        - recipe["projectile"]["anchor"][axis]
        for axis in (0, 1)
    )
    projectile_component = Component(
        projectile_width,
        projectile_height,
        projectile,
        (projectile_position[0] + shake[0], projectile_position[1] + shake[1]),
        255,
        (0, 0),
    )
    return {
        "background": _place(
            background_width, background_height, background, (-4, -4), shake
        ),
        "stars": _place(
            recipe["canvas"]["width"], recipe["canvas"]["height"], stars, (0, 0), shake
        ),
        "wizard": _place(width, height, wizard, position, shake),
        "gem": _place(gem_width, gem_height, gem_pixels, gem_local, shake, gem_opacity),
        "sparks": _place(160, 160, _sparks(recipe, index), effect_local, shake),
        "burst": _place(160, 160, burst, effect_local, shake),
        "projectile": projectile_component,
    }


def target_component(recipe: dict) -> Component:
    width, height, pixels = _read(recipe, "target")
    return Component(width, height, pixels)
