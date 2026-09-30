"""Small real-tool tracer before authoring the full wizard."""

import argparse
import json
from pathlib import Path

from examples.wizard_cast.workflow import Spa, paint_steps, target


def build_probe(executable: str, aseprite: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    spa = Spa(executable, aseprite, output / "operations.jsonl")
    source = output / "source.aseprite"
    spa.call(
        "sprite create",
        target_sprite_file=str(source),
        width=16,
        height=16,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=False,
    )
    spa.mutate(
        "image resize",
        source,
        target=target(1, 1),
        width=5,
        height=5,
        method="nearest-neighbor",
        position_policy={"kind": "keep"},
    )
    steps = paint_steps(
        1, 1, 5, 5, {(x, y): "#6febff" for y in range(5) for x in range(5)}
    )
    steps.extend(
        [
            {
                "operation": "frame duplicate",
                "input": {
                    "source_frame_number": frame,
                    "cel_mode": "copy",
                    "duration_ms": 100,
                },
            }
            for frame in (1, 2)
        ]
    )
    spa.application.plan(source, steps)
    for frame, (x, y) in enumerate(((5, 5), (9, 7), (11, 5)), 1):
        spa.mutate(
            "cel set",
            source,
            target=target(1, frame),
            position={"x": x, "y": y},
            opacity=0 if frame == 3 else 255,
        )
    spa.mutate(
        "image resize",
        source,
        target=target(1, 2),
        width=7,
        height=7,
        method="nearest-neighbor",
        position_policy={
            "kind": "pivot",
            "pivot_x": 2,
            "pivot_y": 2,
            "rounding": "floor",
        },
    )
    positions = [
        spa.call("cel get", sprite_file=str(source), target=target(1, frame))["cel"][
            "position"
        ]
        for frame in (1, 2, 3)
    ]
    component = output / "component.aseprite"
    spa.call(
        "sprite copy",
        source_sprite_file=str(source),
        target_sprite_file=str(component),
        overwrite=False,
    )
    for frame in (1, 2, 3):
        coordinate = 2 if frame == 2 else 3
        spa.mutate(
            "cel set",
            component,
            target=target(1, frame),
            position={"x": coordinate, "y": coordinate},
        )
    spa.mutate(
        "sprite crop",
        component,
        coordinate_space="canvas-pixel",
        rectangle={"x": 0, "y": 0, "width": 11, "height": 11},
    )
    frames = []
    for frame in (1, 2, 3):
        destination = output / f"frame-{frame}.png"
        spa.delivery.export(component, frame, destination)
        frames.append(str(destination))
    evidence = {
        "frames": frames,
        "source_positions": [[v["x"], v["y"]] for v in positions],
        "calls": spa.calls,
        "elapsed_seconds": spa.seconds,
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spa", required=True)
    parser.add_argument("--aseprite", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    print(
        json.dumps(
            build_probe(arguments.spa, arguments.aseprite, arguments.output.resolve()),
            indent=2,
        )
    )
