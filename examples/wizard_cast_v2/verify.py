"""Independently decode SPA artifacts and compare complete recipe builds."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from examples.wizard_cast_v2 import art


def inspect_build(root: Path) -> dict:
    bundle = json.loads((root / "assets/bundle.json").read_text())
    recipe = json.loads((root / "recipe.json").read_text())
    inputs_path = root / "evidence/inputs.json"
    inputs = json.loads(inputs_path.read_text())
    assert {"inputs/preparation.json", "inputs/provenance.json"} <= inputs.keys()
    build = json.loads((root / "evidence/build.json").read_text())
    assert (
        build["inputs_sha256"] == hashlib.sha256(inputs_path.read_bytes()).hexdigest()
    )
    assert (
        build["recipe_sha256"]
        == hashlib.sha256((root / "recipe.json").read_bytes()).hexdigest()
    )
    observation = json.loads((root / "evidence/sprite.json").read_text())
    sprite = {
        key: observation[key]
        for key in ("metadata", "frames", "layers", "cels", "tags")
    }
    assert bundle["canvas"] == {
        key: recipe["canvas"][key] for key in ("width", "height")
    }
    assert sprite["metadata"]["width"] == recipe["canvas"]["width"]
    assert sprite["metadata"]["height"] == recipe["canvas"]["height"]
    assert len(bundle["frames"]) == 32
    assert bundle["cast"]["release_frame"] == recipe["gameplay"]["cast_frame"] + 1 == 15
    release_gem = art.sample_frame(recipe, recipe["gameplay"]["cast_frame"])["gem"]
    wizard = recipe["export"]["components"]["wizard"]
    assert bundle["cast"]["muzzle"] == {
        axis: release_gem.local_position[index]
        + recipe["gem"]["anchor"][index]
        - wizard["crop"][axis]
        - wizard["anchor"][index]
        for index, axis in enumerate(("x", "y"))
    }
    assert [
        (phase["name"], phase["from_frame"], phase["to_frame"], phase["loop"])
        for phase in bundle["phases"]
    ] == [
        ("idle", 1, 4, True),
        ("charge", 5, 14, False),
        ("cast", 15, 20, False),
        ("recover", 21, 32, False),
    ]
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
    assert all(frame["duration_ms"] == 100 for frame in sprite["frames"])
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
    assert len(allowed) == 24
    assert bundle["palette"] == recipe["palette"]
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
    assert len(pixels) == 193
    assert len(list((root / "source").glob("*.aseprite"))) == 7
    assert set(bundle["components"]) == {
        "wizard",
        "gem",
        "burst",
        "projectile",
        "background",
        "target",
    }
    assert {name for name in pixels if name.startswith("scene/")} == {
        f"scene/{frame:04}.png" for frame in range(1, 33)
    }
    for frame in range(1, 33):
        assert pixels[f"scene/{frame:04}.png"]["size"] == [
            recipe["canvas"]["width"],
            recipe["canvas"]["height"],
        ]
    for name, component in bundle["components"].items():
        definition = (
            recipe["export"]["target"]
            if name == "target"
            else recipe["export"]["components"][name]
        )
        size = definition if name == "target" else definition["crop"]
        assert component["size"] == {key: size[key] for key in ("width", "height")}
        assert component["anchor"] == dict(zip(("x", "y"), definition["anchor"]))
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
    assert len(gem_cels) == 32
    assert all(cel["opacity"] in (0, 255) for cel in sprite["cels"])
    pulse_sizes = {
        pulse["frame"] + 1: (pulse["width"], pulse["height"])
        for pulse in recipe["scale_pulse"]["frames"]
    }
    with Image.open(
        art.ROOT / "inputs/prepared" / recipe["inputs"]["gem"]
    ) as gem_image:
        gem_size = gem_image.size
    for cel in gem_cels:
        assert (cel["bounds"]["width"], cel["bounds"]["height"]) == pulse_sizes.get(
            cel["frame_number"], gem_size
        ), "Native resize changed a non-target Frame"
    assert recipe["scale_pulse"]["sampling"] == "nearest-neighbor"
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
        "inputs": inputs,
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


def compare_delivery(build_root: Path, assets: Path) -> None:
    """Check the checked-in consumer assets against a fresh SPA build."""
    generated = inspect_build(build_root)
    assert json.loads((assets / "bundle.json").read_text()) == generated["bundle"]
    delivered = {
        path.relative_to(assets).as_posix(): path for path in assets.rglob("*.png")
    }
    assert delivered.keys() == generated["pixels"].keys()
    for name, path in delivered.items():
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            assert list(rgba.size) == generated["pixels"][name]["size"], name
            assert (
                hashlib.sha256(rgba.tobytes()).hexdigest()
                == generated["pixels"][name]["rgba_sha256"]
            ), name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path, nargs="?")
    parser.add_argument("--delivered-assets", type=Path)
    args = parser.parse_args()
    result = (
        compare_builds(args.first, args.second)
        if args.second
        else inspect_build(args.first)
    )
    if args.delivered_assets:
        compare_delivery(args.first, args.delivered_assets)
    print(json.dumps(result, indent=2))
