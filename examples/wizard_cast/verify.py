"""Independently decode SPA artifacts and compare complete recipe builds."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def inspect_build(root: Path) -> dict:
    bundle = json.loads((root / "assets/bundle.json").read_text())
    recipe = json.loads((root / "recipe.json").read_text())
    observation = json.loads((root / "evidence/sprite.json").read_text())
    sprite = {
        key: observation[key] for key in ("metadata", "frames", "layers", "cels", "tags")
    }
    assert bundle["canvas"] == {"width": 128, "height": 96}
    assert sprite["metadata"]["width"] == 128
    assert sprite["metadata"]["height"] == 96
    assert sprite["metadata"]["color_mode"] == "rgb"
    assert sprite["metadata"]["frame_count"] == len(bundle["frames"])
    assert [phase["name"] for phase in bundle["phases"]] == [
        "idle",
        "charge",
        "cast",
        "recover",
    ]
    assert [tag["name"] for tag in sprite["tags"]] == [
        "IDLE",
        "CHARGE",
        "CAST",
        "RECOVER",
    ]
    assert all(83 <= frame["duration_ms"] <= 125 for frame in sprite["frames"])
    assert [
        {"frame_number": f["frame_number"], "duration_ms": f["duration_ms"]}
        for f in bundle["frames"]
    ] == sprite["frames"]
    covered = []
    for phase, tag in zip(bundle["phases"], sprite["tags"], strict=True):
        assert (phase["from_frame"], phase["to_frame"]) == (
            tag["from_frame"],
            tag["to_frame"],
        )
        covered.extend(range(phase["from_frame"], phase["to_frame"] + 1))
    assert covered == list(range(1, len(bundle["frames"]) + 1))
    assert not json.loads((root / "evidence/audit.json").read_text())["findings"]
    allowed = {
        tuple(bytes.fromhex(value.removeprefix("#")))
        for value in recipe["palette"].values()
    }
    assert 20 <= len(allowed) <= 28
    pixels = {}
    visible_bounds = {}
    for filename in sorted((root / "assets").rglob("*.png")):
        relative = filename.relative_to(root / "assets").as_posix()
        with Image.open(filename) as image:
            rgba = image.convert("RGBA")
            data = rgba.tobytes()
            used = set(zip(data[0::4], data[1::4], data[2::4], data[3::4]))
            assert all(pixel[3] in (0, 255) for pixel in used), relative
            assert all(pixel[:3] in allowed for pixel in used if pixel[3]), relative
            pixels[relative] = {
                "size": list(rgba.size),
                "rgba_sha256": hashlib.sha256(data).hexdigest(),
            }
            visible_bounds[relative] = rgba.getbbox()
    for name, component in bundle["components"].items():
        expected_size = [component["size"]["width"], component["size"]["height"]]
        assert 0 <= component["anchor"]["x"] < expected_size[0]
        assert 0 <= component["anchor"]["y"] < expected_size[1]
        frames = component["frames"]
        assert len(frames) == (1 if name == "target" else len(bundle["frames"]))
        assert [frame["frame_number"] for frame in frames] == list(
            range(1, len(frames) + 1)
        )
        for frame in frames:
            assert pixels[frame["path"]]["size"] == expected_size
            if name in ("wizard", "target", "background"):
                assert visible_bounds[frame["path"]] is not None
    cast = next(phase for phase in bundle["phases"] if phase["name"] == "cast")
    for frame in range(cast["from_frame"], cast["to_frame"] + 1):
        assert visible_bounds[f"projectile/{frame:04}.png"] is not None
    gem_path = next(
        layer["path"] for layer in sprite["layers"] if layer["name"] == "gem"
    )
    gem_cels = [cel for cel in sprite["cels"] if cel["layer_path"] == gem_path]
    assert {cel["opacity"] for cel in gem_cels} == {0, 255}
    for pulse in recipe["scale_pulse"]["frames"]:
        cel = next(cel for cel in gem_cels if cel["frame_number"] == pulse["frame"] + 1)
        assert (cel["bounds"]["width"], cel["bounds"]["height"]) == (
            pulse["width"],
            pulse["height"],
        )
        result = json.loads(
            (root / f"evidence/scale-{pulse['frame'] + 1}.json").read_text()
        )
        assert len(result["affected_cels"]) == 1
        assert result["position_policy"] == {
            "kind": recipe["scale_pulse"]["cel_position_policy"],
            "pivot_x": recipe["scale_pulse"]["pivot"][0],
            "pivot_y": recipe["scale_pulse"]["pivot"][1],
            "rounding": recipe["scale_pulse"]["rounding"],
        }
    return {
        "sprite": sprite,
        "bundle": bundle,
        "pixels": pixels,
        "visible_bounds": visible_bounds,
    }


def compare_builds(first: Path, second: Path) -> dict:
    left, right = inspect_build(first), inspect_build(second)
    assert left == right, (
        "Recipe builds differ in saved structure, metadata, or decoded pixels"
    )
    return {
        "same_structure": True,
        "same_decoded_pixels": True,
        "frame_count": len(left["bundle"]["frames"]),
        "png_count": len(left["pixels"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path, nargs="?")
    args = parser.parse_args()
    result = (
        compare_builds(args.first, args.second)
        if args.second
        else inspect_build(args.first)
    )
    print(json.dumps(result, indent=2))
