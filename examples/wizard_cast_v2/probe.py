"""Prove generated raster pixels survive public SPA authoring and persistence."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from examples.wizard_cast_v2.raster import read_pixels
from examples.wizard_cast_v2.workflow import Spa, paint_steps, target

ROOT = Path(__file__).parent


def build_probe(executable: str, aseprite: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    spec = json.loads((ROOT / "inputs/preparation.json").read_text())
    image_path = ROOT / "inputs/prepared/idle.png"
    width, height, pixels = read_pixels(image_path, spec["palette"])
    spa = Spa(executable, aseprite, output / "operations.jsonl")
    source = output / "handoff.aseprite"
    runtime = spa.call("info")
    spa.call(
        "sprite create",
        target_sprite_file=str(source),
        width=width + 4,
        height=height + 4,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=False,
    )
    spa.mutate(
        "image resize",
        source,
        target=target(1, 1),
        width=width,
        height=height,
        method="nearest-neighbor",
        position_policy={"kind": "keep"},
    )
    steps = paint_steps(
        1,
        1,
        width,
        height,
        {coordinate: spec["palette"][name] for coordinate, name in pixels.items()},
    )
    steps.extend(
        {
            "operation": "frame duplicate",
            "input": {
                "source_frame_number": frame,
                "cel_mode": "copy",
                "duration_ms": 100,
            },
        }
        for frame in (1, 2)
    )
    for offset in range(0, len(steps), 64):
        spa.plan(source, steps[offset : offset + 64])
    for frame, position in enumerate(((0, 0), (2, 1), (0, 0)), 1):
        spa.mutate(
            "cel set",
            source,
            target=target(1, frame),
            position={"x": position[0], "y": position[1]},
            opacity=0 if frame == 3 else 255,
        )
    reopened = spa.call(
        "sprite get",
        sprite_file=str(source),
        inspection_scope=["frames", "layers", "cels"],
    )
    frames = []
    with Image.open(image_path) as original:
        prepared = original.convert("RGBA")
    for frame, position in enumerate(((0, 0), (2, 1), (0, 0)), 1):
        destination = output / f"frame-{frame}.png"
        spa.export(source, frame, destination)
        expected = Image.new("RGBA", (width + 4, height + 4))
        expected.paste(prepared, position)
        if frame == 3:
            # Aseprite keeps RGB under zero alpha when Cel opacity hides an Image.
            # Check that path explicitly instead of assuming transparent black.
            expected.putalpha(0)
        with Image.open(destination) as exported:
            actual = exported.convert("RGBA")
            assert actual.size == expected.size
            assert actual.tobytes() == expected.tobytes(), (
                f"Pixel handoff mismatch in Frame {frame}"
            )
            frames.append(
                {
                    "path": str(destination),
                    "rgba_sha256": hashlib.sha256(actual.tobytes()).hexdigest(),
                }
            )
    evidence = {
        "runtime": runtime,
        "input_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "reopened": reopened,
        "pixel_correspondence": True,
        "frames": frames,
        "calls": spa.calls,
        "cli_elapsed_seconds": spa.seconds,
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spa", required=True)
    parser.add_argument("--aseprite", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            build_probe(args.spa, args.aseprite, args.output.resolve()), indent=2
        )
    )
