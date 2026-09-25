"""Sample the finite wizard recipe into palette-colored pixel runs.

This module supplies authoring inputs. SPA owns Images, Cels, Frames, painting,
the declared resize pulse, and exported artifacts. Omitted pixels are transparent.
All frame numbers in this module and the recipe are zero-based.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

Pixels = dict[tuple[int, int], str]


@dataclass(frozen=True)
class Component:
    """One fixed-size Image and its scene and normalized Cel positions."""

    width: int
    height: int
    pixels: Pixels
    position: tuple[int, int]
    opacity: int = 255
    local_position: tuple[int, int] = (0, 0)


def load_recipe(path: str | Path | None = None) -> dict[str, Any]:
    """Read the example-owned finite inputs, with no external dependencies."""
    recipe_path = (
        Path(path) if path is not None else Path(__file__).with_name("recipe.json")
    )
    return json.loads(recipe_path.read_text(encoding="utf-8"))


def total_frames(recipe: dict[str, Any]) -> int:
    return sum(phase["frames"] for phase in recipe["phases"])


def phases(recipe: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the four contiguous ranges without adding a terminal idle range."""
    result = []
    start = 0
    for phase in recipe["phases"]:
        result.append({**phase, "start": start, "end": start + phase["frames"] - 1})
        start += phase["frames"]
    return result


def _round(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _ease(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def _rect(pixels: Pixels, x: int, y: int, width: int, height: int, color: str) -> None:
    for row in range(y, y + height):
        for column in range(x, x + width):
            pixels[column, row] = color


def _run(pixels: Pixels, y: int, left: int, right: int, color: str) -> None:
    _rect(pixels, left, y, right - left + 1, 1, color)


def _line(
    pixels: Pixels, start: tuple[int, int], end: tuple[int, int], color: str
) -> None:
    """Rasterize an integer line into one-pixel runs, with no antialiasing."""
    x, y = start
    last_x, last_y = end
    dx, dy = abs(last_x - x), -abs(last_y - y)
    step_x, step_y = (1 if x < last_x else -1), (1 if y < last_y else -1)
    error = dx + dy
    while True:
        pixels[x, y] = color
        if (x, y) == (last_x, last_y):
            return
        doubled = error * 2
        if doubled >= dy:
            error += dy
            x += step_x
        if doubled <= dx:
            error += dx
            y += step_y


def _stamp(
    pixels: Pixels, x: int, y: int, rows: tuple[str, ...], colors: dict[str, str]
) -> None:
    for row_index, row in enumerate(rows):
        for column, character in enumerate(row):
            if character != ".":
                pixels[x + column, y + row_index] = colors[character]


def _pose(recipe: dict[str, Any], frame: int, phase: dict[str, Any]) -> dict[str, int]:
    keyframes = recipe["pose"]["keyframes"]
    left, right = keyframes[0], keyframes[-1]
    for first, second in pairwise(keyframes):
        if first["frame"] <= frame <= second["frame"]:
            left, right = first, second
            break
    amount = _ease((frame - left["frame"]) / (right["frame"] - left["frame"]))
    pose = {
        key: _round(left[key] + (right[key] - left[key]) * amount)
        for key in left
        if key != "frame"
    }
    if phase["name"] == "idle":
        pose["bob"] = recipe["pose"]["idle_bob"][frame - phase["start"]]
        pose["beard_sway"] = recipe["pose"]["idle_beard_sway"][frame - phase["start"]]
    return pose


def _background(recipe: dict[str, Any]) -> Pixels:
    pixels: Pixels = {}
    margin = recipe["scene"]["overscan"]
    width, height = recipe["canvas"]["width"], recipe["canvas"]["height"]
    _rect(pixels, -margin, -margin, width + margin * 2, height + margin * 2, "sky")

    # Stepped cloud silhouettes and distant masonry use flat palette colors.
    for x, y, cloud_width in (
        (3, 25, 22),
        (8, 24, 12),
        (60, 15, 15),
        (64, 14, 7),
        (91, 47, 28),
        (97, 46, 17),
    ):
        _rect(pixels, x, y, cloud_width, 1, "sky_high")
    for x, top, tower_width in ((0, 68, 15), (77, 66, 11), (95, 62, 14), (114, 68, 14)):
        _rect(pixels, x, top, tower_width, 13, "sky_high")
        _run(pixels, top - 1, x + 2, x + tower_width - 3, "sky_high")
        _rect(pixels, x + 3, top + 3, 2, 3, "sky")
    _rect(pixels, 85, 72, 31, 7, "sky_high")

    moon_x, moon_y = recipe["scene"]["moon_center"]
    moon_runs = (3, 5, 6, 7, 7, 8, 8, 8, 8, 8, 7, 7, 6, 5, 3)
    for index, half_width in enumerate(moon_runs):
        y = moon_y - 7 + index
        _run(pixels, y, moon_x - half_width, moon_x + half_width, "moon")
        _run(pixels, y, moon_x - half_width, moon_x - half_width + 1, "moon_shadow")
    # The offset bite makes a readable crescent at the native pixel size.
    for index, half_width in enumerate((2, 4, 5, 6, 6, 7, 7, 7, 7, 7, 6, 6, 5, 4, 2)):
        _run(
            pixels,
            moon_y - 8 + index,
            moon_x - 5 - half_width,
            moon_x - 5 + half_width,
            "sky",
        )
    for x, y in ((105, 17), (104, 23), (100, 25)):
        pixels[x, y] = "white"

    ground = recipe["scene"]["ground_y"]
    _rect(
        pixels,
        -margin,
        ground + 1,
        width + margin * 2,
        height - ground + margin - 1,
        "stone",
    )
    _run(pixels, ground, -margin, width + margin - 1, "stone_light")
    _run(pixels, ground + 1, -margin, width + margin - 1, "stone_shadow")
    _run(pixels, ground + 9, -margin, width + margin - 1, "stone_shadow")
    for x in (10, 37, 68, 94, 120):
        _rect(pixels, x, ground + 2, 1, 7, "stone_shadow")
        _run(pixels, ground + 2, x + 2, x + 8, "stone_light")
    for x in (23, 54, 82, 110):
        _rect(pixels, x, ground + 10, 1, 9, "stone_shadow")
    for x, y, length in (
        (3, 93, 10),
        (44, 85, 5),
        (78, 94, 7),
        (101, 84, 8),
        (116, 94, 5),
    ):
        _run(pixels, y, x, x + length, "stone_light")
    for x in (8, 71, 116):
        _rect(pixels, x, ground - 3, 1, 3, "stone_shadow")
        pixels[x - 1, ground - 2] = "stone_shadow"
        pixels[x + 1, ground - 1] = "stone_shadow"
    return {(x + margin, y + margin): color for (x, y), color in pixels.items()}


def _stars(recipe: dict[str, Any], frame: int) -> Pixels:
    settings = recipe["scene"]["stars"]
    rng = random.Random(settings["seed"])
    left, top, right, bottom = settings["bounds"]
    margin = recipe["scene"]["overscan"]
    moon_x, moon_y = recipe["scene"]["moon_center"]
    positions: list[tuple[int, int, int]] = []
    while len(positions) < settings["count"]:
        x, y = rng.randrange(left, right), rng.randrange(top, bottom)
        if abs(x - moon_x) < 13 and abs(y - moon_y) < 13:
            continue
        if any(old_x == x and old_y == y for old_x, old_y, _ in positions):
            continue
        positions.append((x, y, rng.randrange(settings["twinkle_period"])))
    return {
        (x + margin, y + margin): settings["colors"][
            (frame + offset) % settings["twinkle_period"]
        ]
        for x, y, offset in positions
    }


def _wizard(
    recipe: dict[str, Any], pose: dict[str, int], phase: dict[str, Any], frame: int
) -> tuple[Pixels, tuple[int, int]]:
    pixels: Pixels = {}
    base_x, base_y = recipe["pose"]["staff_base"]
    length = recipe["pose"]["staff_length"] + pose["arm_raise"]
    angle = math.radians(pose["staff_angle"])
    staff_top = (
        base_x + _round(math.sin(angle) * length),
        base_y - _round(math.cos(angle) * length),
    )
    gem_center = staff_top[0], staff_top[1] - 3

    for offset in (-1, 0, 1):
        _line(
            pixels,
            (base_x + offset, base_y),
            (staff_top[0] + offset, staff_top[1]),
            "ink",
        )
    _line(pixels, (base_x, base_y - 1), staff_top, "wood")
    for y in range(staff_top[1] + 3, base_y - 1, 6):
        x = _round(
            staff_top[0]
            + (base_x - staff_top[0]) * (y - staff_top[1]) / (base_y - staff_top[1])
        )
        pixels[x, y] = "gold"
    _run(pixels, gem_center[1] + 2, gem_center[0] - 3, gem_center[0] + 3, "ink")
    _run(pixels, gem_center[1] + 2, gem_center[0] - 2, gem_center[0] + 2, "gold")
    pixels[gem_center[0] - 3, gem_center[1] + 1] = "gold"
    pixels[gem_center[0] + 3, gem_center[1] + 1] = "gold"

    _rect(pixels, 6, 35, 8, 4, "ink")
    _rect(pixels, 16, 35, 7, 4, "ink")
    _run(pixels, 37, 6, 11, "leather")
    _run(pixels, 37, 17, 21, "leather")
    pixels[7, 37] = "gold"
    pixels[19, 37] = "gold"

    robe_edges = (
        (9, 19),
        (8, 20),
        (8, 21),
        (7, 21),
        (7, 22),
        (7, 22),
        (6, 22),
        (6, 23),
        (6, 23),
        (5, 23),
        (5, 23),
        (4, 24),
        (4, 24),
        (3, 25),
        (3, 25),
        (5, 24),
    )
    for row, (left, right) in enumerate(robe_edges, start=21):
        sway = pose["robe_sway"] if row >= 30 else 0
        left, right = left + sway, right + sway
        _run(pixels, row, left, right, "ink")
        _run(pixels, row, left + 1, right - 1, "robe_dark")
        _run(pixels, row, max(left + 2, 11 + sway), right - 2, "robe")
        if row > 26:
            _run(pixels, row, 17 + sway, min(right - 2, 19 + sway), "robe_light")
    _run(pixels, 28, 7, 22, "leather")
    _rect(pixels, 17, 28, 3, 2, "gold")
    pixels[18, 28] = "robe_dark"
    _run(pixels, 35, 5 + pose["robe_sway"], 23 + pose["robe_sway"], "gold")
    _rect(pixels, 7, 24, 3, 6, "robe_dark")
    _rect(pixels, 7, 29, 3, 2, "skin")
    pixels[7, 30] = "wood"

    # The raised sleeve has a stepped contour and a small visible hand.
    shoulder, hand = (19, 23), (25, 23 - pose["arm_raise"])
    for offset in range(-2, 3):
        _line(
            pixels,
            (shoulder[0], shoulder[1] + offset),
            (hand[0], hand[1] + offset),
            "ink",
        )
    for offset in (-1, 0, 1):
        _line(
            pixels,
            (shoulder[0], shoulder[1] + offset),
            (hand[0] - 1, hand[1] + offset),
            "robe_dark" if offset == 1 else "robe",
        )
    _line(
        pixels, (shoulder[0], shoulder[1] - 1), (hand[0] - 1, hand[1] - 1), "robe_light"
    )
    _rect(pixels, hand[0] - 1, hand[1] - 1, 2, 3, "skin")
    pixels[hand[0], hand[1] + 1] = "wood"

    tilt = pose["head_tilt"]
    _rect(pixels, 11 + tilt, 14, 10, 7, "ink")
    _rect(pixels, 12 + tilt, 15, 8, 5, "skin")
    _run(pixels, 17, 20 + tilt, 22 + tilt, "skin")
    pixels[19 + tilt, 16] = "ink"
    pixels[18 + tilt, 15] = "white"
    pixels[20 + tilt, 18] = "wood"

    beard_edges = (
        (10, 19),
        (9, 20),
        (9, 20),
        (10, 19),
        (10, 18),
        (11, 18),
        (11, 17),
        (12, 17),
        (12, 16),
        (13, 16),
        (13, 15),
        (14, 15),
    )
    for row, (left, right) in enumerate(beard_edges, start=19):
        sway = pose["beard_sway"] if row > 23 else tilt
        left, right = left + sway, right + sway
        _run(pixels, row, left, right, "ink")
        if right - left > 1:
            _run(pixels, row, left + 1, right - 1, "beard_shadow")
            _run(pixels, row, left + 1, max(left + 1, right - 3), "beard")
    _run(pixels, 19, 11 + tilt, 18 + tilt, "beard")
    pixels[15 + tilt, 20] = "beard_shadow"
    pixels[12 + tilt, 22] = "white"
    pixels[15 + pose["beard_sway"], 25] = "beard"

    _stamp(
        pixels,
        4 + tilt,
        3,
        (
            "....oooo...........",
            "...ohhho...........",
            "...ohhhho..........",
            ".....ohhho.........",
            "......ohhho........",
            ".....ohhHhho.......",
            ".....ohhHHhho......",
            "....ohhHHHHhho.....",
            "...ohhHHHHHHhho....",
            "...oggggggggggo....",
            "..ohhHHHHHHHHHho...",
            "ooooooooooooooooooo",
        ),
        {"o": "ink", "h": "hat", "H": "hat_light", "g": "gold"},
    )
    pixels[14 + tilt, 12] = "moon"

    rim = "magic_dark"
    if phase["name"] == "charge" and frame - phase["start"] >= 3:
        rim = "magic"
    if phase["name"] == "cast":
        rim = "magic_light"
    for row in range(24, 35):
        sway = pose["robe_sway"] if row >= 30 else 0
        pixels[robe_edges[row - 21][1] - 1 + sway, row] = rim
    for x, y in ((13, 8), (14, 9), (15, 10), (16, 11)):
        pixels[x + tilt, y] = rim
    return pixels, gem_center


def _gem_offset(recipe: dict[str, Any], frame: int) -> tuple[int, int]:
    keys = recipe["gem"]["position_keyframes"]
    for left, right in pairwise(keys):
        if left["frame"] <= frame <= right["frame"]:
            amount = _ease((frame - left["frame"]) / (right["frame"] - left["frame"]))
            return tuple(
                _round(a + (b - a) * amount)
                for a, b in zip(left["offset"], right["offset"])
            )
    return tuple(keys[-1]["offset"])


def _gem_pixels() -> Pixels:
    pixels: Pixels = {}
    _stamp(
        pixels,
        0,
        0,
        ("..d..", ".dld.", "dwlmd", ".dmd.", "..d.."),
        {
            "d": "magic_dark",
            "m": "magic",
            "l": "magic_light",
            "w": "white",
        },
    )
    return pixels


def _sparks(recipe: dict[str, Any], frame: int, ranges: list[dict[str, Any]]) -> Pixels:
    settings = recipe["particles"]
    rng = random.Random(settings["seed"])
    charge, cast = ranges[1], ranges[2]
    pixels: Pixels = {}
    for index in range(settings["count"]):
        angle = math.radians(rng.randrange(360))
        radius_jitter = rng.randrange(-1, 2)
        for name, start in (("charge", charge["start"]), ("cast", cast["start"])):
            path = settings[name]
            age = frame - start - index % path["birth_spread"]
            if not 0 <= age < path["lifetime"] - 1:
                continue
            progress = age / (path["lifetime"] - 1)
            distance = path["radius_start"] + (
                path["radius_end"] - path["radius_start"]
            ) * _ease(progress)
            distance += radius_jitter
            turn = angle + progress * math.tau * path["turns"]
            x = 20 + _round(math.cos(turn) * distance)
            y = 20 + _round(math.sin(turn) * distance)
            color_index = next(
                i for i, end in enumerate(settings["color_frames"]) if age < end
            )
            color = settings["colors"][color_index]
            pixels[x, y] = color
            if age < 2 and index % 3 == 0:
                pixels[x - 1, y] = color
            elif 2 <= age < 4:
                trail_x = x - (1 if math.cos(turn) >= 0 else -1)
                pixels[trail_x, y] = "magic_dark"
    return pixels


def _burst(recipe: dict[str, Any], frame: int, cast: dict[str, Any]) -> Pixels:
    pixels: Pixels = {}
    offset = frame - cast["start"]
    if not 0 <= offset < len(recipe["burst"]["radii"]):
        return pixels
    radius = recipe["burst"]["radii"][offset]
    if radius == 0:
        return pixels
    outer, middle, light, center = recipe["burst"]["colors"]
    for dy in range(-radius, radius + 1):
        half_width = max(0, (radius - abs(dy)) // 3)
        _run(pixels, 20 + dy, 20 - half_width, 20 + half_width, outer)
    for dx in range(-radius, radius + 1):
        half_height = max(0, (radius - abs(dx)) // 3)
        _rect(pixels, 20 + dx, 20 - half_height, 1, half_height * 2 + 1, middle)
    diagonal = max(1, radius // 2)
    for direction_x, direction_y in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        _line(
            pixels,
            (20, 20),
            (20 + diagonal * direction_x, 20 + diagonal * direction_y),
            middle,
        )
    for dy in range(-3, 4):
        half_width = max(0, 3 - abs(dy))
        _run(pixels, 20 + dy, 20 - half_width, 20 + half_width, light)
    _run(pixels, 20, 18, 22, center)
    _rect(pixels, 20, 18, 1, 5, center)
    return pixels


def _projectile(recipe: dict[str, Any], offset: int) -> Pixels:
    pixels: Pixels = {}
    if not 0 <= offset < len(recipe["projectile"]["centers"]):
        return pixels
    tail = recipe["projectile"]["trail_lengths"][offset]
    for y, left, right, color in (
        (2, 12, 14, "magic_dark"),
        (3, 10, 16, "magic_dark"),
        (4, 8, 17, "magic"),
        (5, 13 - tail, 18, "magic"),
        (6, 13 - tail, 18, "magic_light"),
        (7, 7, 17, "magic"),
        (8, 10, 16, "magic_dark"),
        (9, 12, 14, "magic_dark"),
    ):
        _run(pixels, y, left, right, color)
    _run(pixels, 5, 12, 15, "magic_light")
    _run(pixels, 6, 11, 16, "white")
    _run(pixels, 7, 12, 15, "magic_light")
    _run(pixels, 4, 13 - tail, 8, "magic_dark")
    pixels[11 - tail, 8] = "magic_dark"
    return pixels


def sample_frame(recipe: dict[str, Any], zero_based_frame: int) -> dict[str, Component]:
    """Evaluate one finite Frame; the caller applies the declared SPA resize."""
    if not 0 <= zero_based_frame < total_frames(recipe):
        raise ValueError("Frame index is outside the finite recipe.")
    frame = zero_based_frame
    ranges = phases(recipe)
    phase = next(item for item in ranges if item["start"] <= frame <= item["end"])
    pose = _pose(recipe, frame, phase)
    shake = next(
        (item["offset"] for item in recipe["scene"]["shake"] if item["frame"] == frame),
        (0, 0),
    )

    def component(
        width: int,
        height: int,
        pixels: Pixels,
        local: tuple[int, int],
        opacity: int = 255,
        world: tuple[int, int] | None = None,
    ) -> Component:
        x, y = local if world is None else world
        return Component(
            width, height, pixels, (x + shake[0], y + shake[1]), opacity, local
        )

    wizard_pixels, staff_gem = _wizard(recipe, pose, phase, frame)
    wizard_x, wizard_y = recipe["pose"]["position"]
    wizard_y += pose["bob"]
    offset_x, offset_y = _gem_offset(recipe, frame)
    gem_center = wizard_x + staff_gem[0] + offset_x, wizard_y + staff_gem[1] + offset_y
    gem_opacity = 255
    for keyframe in recipe["gem"]["opacity_keyframes"]:
        if keyframe["frame"] <= frame:
            gem_opacity = keyframe["opacity"]
    cast_offset = frame - ranges[2]["start"]
    projectile_world = (0, 0)
    if 0 <= cast_offset < len(recipe["projectile"]["centers"]):
        center_x, center_y = recipe["projectile"]["centers"][cast_offset]
        anchor_x, anchor_y = recipe["projectile"]["anchor"]
        projectile_world = center_x - anchor_x, center_y - anchor_y
    margin = recipe["scene"]["overscan"]
    width, height = recipe["canvas"]["width"], recipe["canvas"]["height"]
    return {
        "background": component(
            width + 2 * margin,
            height + 2 * margin,
            _background(recipe),
            (-margin, -margin),
        ),
        "stars": component(
            width + 2 * margin,
            height + 2 * margin,
            _stars(recipe, frame),
            (-margin, -margin),
        ),
        "wizard": component(32, 40, wizard_pixels, (wizard_x, wizard_y)),
        "gem": component(
            5, 5, _gem_pixels(), (gem_center[0] - 2, gem_center[1] - 2), gem_opacity
        ),
        "sparks": component(
            40,
            40,
            _sparks(recipe, frame, ranges),
            (gem_center[0] - 20, gem_center[1] - 20),
        ),
        "burst": component(
            40,
            40,
            _burst(recipe, frame, ranges[2]),
            (gem_center[0] - 20, gem_center[1] - 20),
        ),
        "projectile": component(
            *recipe["projectile"]["size"],
            _projectile(recipe, cast_offset),
            (0, 0),
            world=projectile_world,
        ),
    }


def target_component(recipe: dict[str, Any]) -> Component:
    """Return the separate practice target, authored from the same palette."""
    pixels: Pixels = {}
    _rect(pixels, 8, 17, 5, 10, "ink")
    _rect(pixels, 9, 18, 3, 8, "wood")
    _rect(pixels, 10, 19, 1, 6, "gold")
    _run(pixels, 26, 5, 15, "ink")
    _run(pixels, 25, 7, 13, "leather")
    outer_widths = (3, 5, 6, 7, 8, 8, 8, 8, 8, 8, 8, 7, 6, 5, 3)
    for row, radius in enumerate(outer_widths, start=2):
        _run(pixels, row, 10 - radius, 10 + radius, "ink")
        _run(pixels, row, 11 - radius, 9 + radius, "gold")
    for row, radius in enumerate((2, 4, 5, 6, 6, 6, 6, 6, 5, 4, 2), start=4):
        _run(pixels, row, 10 - radius, 10 + radius, "leather")
        _run(pixels, row, 11 - radius, 9 + radius, "robe")
    for dy in range(-3, 4):
        radius = 3 - abs(dy)
        _run(pixels, 9 + dy, 10 - radius, 10 + radius, "robe_dark")
    _rect(pixels, 9, 8, 3, 3, "gold")
    pixels[10, 9] = "white"
    for x, y in ((10, 3), (3, 9), (17, 9), (10, 15)):
        pixels[x, y] = "white"
    return Component(
        recipe["export"]["target"]["width"],
        recipe["export"]["target"]["height"],
        pixels,
        (0, 0),
        local_position=(0, 0),
    )
