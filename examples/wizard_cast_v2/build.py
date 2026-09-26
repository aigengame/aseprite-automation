"""Author the finite wizard recipe through installed SPA and export its assets."""

import argparse
import hashlib
import json
from pathlib import Path

from examples.wizard_cast_v2 import art
from examples.wizard_cast_v2.workflow import Spa, paint_steps, target

ROOT = Path(__file__).parent


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _paint(spa: Spa, source: Path, steps: list[dict]) -> None:
    for offset in range(0, len(steps), 64):
        spa.plan(source, steps[offset : offset + 64])


def _colored(component: art.Component, palette: dict) -> dict:
    return {coordinate: palette[name] for coordinate, name in component.pixels.items()}


def _place(
    spa: Spa, source: Path, layer: int, frame: int, component: art.Component
) -> None:
    spa.mutate(
        "cel set",
        source,
        target=target(layer, frame),
        position={"x": component.position[0], "y": component.position[1]},
        opacity=component.opacity,
    )


def _create(spa: Spa, source: Path, width: int, height: int) -> None:
    spa.call(
        "sprite create",
        target_sprite_file=str(source),
        width=width,
        height=height,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=False,
    )


def build(
    executable: str, aseprite: str, output: Path, recipe_path: Path | None = None
) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    evidence = output / "evidence"
    evidence.mkdir()
    native = output / "source"
    native.mkdir()
    assets = output / "assets"
    assets.mkdir()
    spa = Spa(executable, aseprite, evidence / "operations.jsonl")
    recipe = art.load_recipe(recipe_path)
    sampled = [
        art.sample_frame(recipe, index) for index in range(art.total_frames(recipe))
    ]
    names = list(sampled[0])
    palette = recipe["palette"]
    source = native / "wizard_scene.aseprite"
    write_json(evidence / "runtime.json", spa.call("info"))
    write_json(output / "recipe.json", recipe)
    # Pin all frozen inputs, including the original generations and preparation
    # records. Builds consume these local files without any generation service.
    write_json(
        evidence / "inputs.json",
        {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted((ROOT / "inputs").rglob("*"))
            if path.is_file()
        },
    )
    _create(spa, source, recipe["canvas"]["width"], recipe["canvas"]["height"])
    layer_paths = {names[0]: 1}
    spa.mutate(
        "layer set", source, target={"layer_path": [1]}, properties={"name": names[0]}
    )
    for name in names[1:]:
        result = spa.mutate("layer add", source, kind="transparent", name=name)
        layer_paths[name] = result["layer"]["path"][0]
    _paint(
        spa,
        source,
        [
            {"operation": "cel add", "input": {"target": target(layer_paths[name], 1)}}
            for name in names[1:]
        ],
    )
    for name, component in sampled[0].items():
        if (component.width, component.height) != (
            recipe["canvas"]["width"],
            recipe["canvas"]["height"],
        ):
            spa.mutate(
                "image resize",
                source,
                target=target(layer_paths[name], 1),
                width=component.width,
                height=component.height,
                method="nearest-neighbor",
                position_policy={"kind": "keep"},
            )

    # Copies inherit the first Frame's placement. Set that baseline while the
    # document is small, then change only the Cels that need a different value.
    for name, component in sampled[0].items():
        if component.position != (0, 0) or component.opacity != 255:
            _place(spa, source, layer_paths[name], 1, component)

    # Frame copies keep Images independent. Paint deltas include explicit transparent
    # pixels where an earlier pose has disappeared; only the public Patch writes art.
    steps: list[dict] = []
    frame_facts = []
    for index, frame in enumerate(sampled):
        phase = next(p for p in art.phases(recipe) if p["start"] <= index <= p["end"])
        frame_facts.append(
            {
                "frame_number": index + 1,
                "duration_ms": phase["duration_ms"],
                "phase": phase["name"],
            }
        )
        if index:
            steps.append(
                {
                    "operation": "frame duplicate",
                    "input": {
                        "source_frame_number": index,
                        "cel_mode": "copy",
                        "duration_ms": phase["duration_ms"],
                    },
                }
            )
        for name, component in frame.items():
            current = _colored(component, palette)
            previous = _colored(sampled[index - 1][name], palette) if index else {}
            changed = {
                coordinate: current.get(coordinate)
                for coordinate in previous.keys() | current.keys()
                if previous.get(coordinate) != current.get(coordinate)
            }
            steps.extend(
                paint_steps(
                    layer_paths[name],
                    index + 1,
                    component.width,
                    component.height,
                    changed,
                )
            )
    _paint(spa, source, steps)
    first_duration = frame_facts[0]["duration_ms"]
    if first_duration != 100:
        spa.mutate("frame set", source, frame_number=1, duration_ms=first_duration)
    for index, frame in enumerate(sampled[1:], 1):
        for name, component in frame.items():
            inherited = sampled[0][name]
            if (component.position, component.opacity) != (
                inherited.position,
                inherited.opacity,
            ):
                _place(spa, source, layer_paths[name], index + 1, component)
    pulses = {}
    scale = recipe["scale_pulse"]
    for pulse in scale["frames"]:
        result = spa.mutate(
            "image resize",
            source,
            target=target(layer_paths[scale["component"]], pulse["frame"] + 1),
            width=pulse["width"],
            height=pulse["height"],
            method=scale["sampling"],
            position_policy={
                "kind": scale["cel_position_policy"],
                "pivot_x": scale["pivot"][0],
                "pivot_y": scale["pivot"][1],
                "rounding": scale["rounding"],
            },
        )
        pulses[pulse["frame"]] = (
            result["offset_x"]["applied"],
            result["offset_y"]["applied"],
        )
        write_json(evidence / f"scale-{pulse['frame'] + 1}.json", result)
    phases = [
        {
            "name": p["name"],
            "from_frame": p["start"] + 1,
            "to_frame": p["end"] + 1,
            "loop": p["name"] == "idle",
        }
        for p in art.phases(recipe)
    ]
    for phase in phases:
        spa.mutate(
            "tag add",
            source,
            name=phase["name"].upper(),
            from_frame=phase["from_frame"],
            to_frame=phase["to_frame"],
            direction="forward",
            repeats=0,
        )
    inspection = spa.call(
        "sprite get",
        sprite_file=str(source),
        inspection_scope=["frames", "layers", "cels", "tags"],
    )
    write_json(evidence / "sprite.json", inspection)
    write_json(
        evidence / "audit.json",
        spa.call(
            "animation audit",
            sprite_file=str(source),
            from_frame=1,
            to_frame=len(sampled),
            duration_bounds={"minimum_ms": 83, "maximum_ms": 125},
            required_cels=[
                target(layer, frame + 1)
                for layer in layer_paths.values()
                for frame in range(len(sampled))
            ],
        ),
    )
    write_json(
        evidence / "seam.json",
        spa.call(
            "animation compare",
            sprite_file=str(source),
            earlier_frame=1,
            later_frame=len(sampled),
        ),
    )
    spa.call(
        "animation preview",
        source_sprite_file=str(source),
        earlier_frame=1,
        later_frame=len(sampled),
        destination={"path": str(evidence / "seam.png"), "if_exists": "fail"},
    )

    for index in range(len(sampled)):
        spa.export(source, index + 1, assets / "scene" / f"{index + 1:04}.png")

    components = {}
    for name, definition in recipe["export"]["components"].items():
        print(f"Exporting {name}", flush=True)
        derived = native / f"{name}.aseprite"
        spa.call(
            "sprite copy",
            source_sprite_file=str(source),
            target_sprite_file=str(derived),
            overwrite=False,
        )
        selected = definition["layers"]
        for other in names:
            if other not in selected:
                spa.mutate(
                    "layer set",
                    derived,
                    target={"layer_path": [layer_paths[other]]},
                    properties={"is_visible": False},
                )
        for index, frame in enumerate(sampled):
            for selected_name in selected:
                component = frame[selected_name]
                if component.position != component.local_position:
                    adjustment = (
                        pulses.get(index, (0, 0)) if selected_name == "gem" else (0, 0)
                    )
                    spa.mutate(
                        "cel set",
                        derived,
                        target=target(layer_paths[selected_name], index + 1),
                        position={
                            "x": component.local_position[0] + adjustment[0],
                            "y": component.local_position[1] + adjustment[1],
                        },
                    )
        rectangle = definition["crop"]
        spa.mutate(
            "sprite crop", derived, coordinate_space="canvas-pixel", rectangle=rectangle
        )
        exported = []
        for index in range(len(sampled)):
            relative = f"{name}/{index + 1:04}.png"
            spa.export(derived, index + 1, assets / relative)
            exported.append({"frame_number": index + 1, "path": relative})
        components[name] = {
            "size": {"width": rectangle["width"], "height": rectangle["height"]},
            "anchor": {"x": definition["anchor"][0], "y": definition["anchor"][1]},
            "frames": exported,
        }

    target_art = art.target_component(recipe)
    target_source = native / "target.aseprite"
    _create(spa, target_source, target_art.width, target_art.height)
    _paint(
        spa,
        target_source,
        paint_steps(
            1, 1, target_art.width, target_art.height, _colored(target_art, palette)
        ),
    )
    spa.export(target_source, 1, assets / "target" / "0001.png")
    components["target"] = {
        "size": {"width": target_art.width, "height": target_art.height},
        "anchor": {
            "x": recipe["export"]["target"]["anchor"][0],
            "y": recipe["export"]["target"]["anchor"][1],
        },
        "frames": [{"frame_number": 1, "path": "target/0001.png"}],
    }
    release = recipe["gameplay"]["cast_frame"]
    gem = sampled[release]["gem"]
    wizard_definition = recipe["export"]["components"]["wizard"]
    foot = (
        wizard_definition["crop"]["x"] + wizard_definition["anchor"][0],
        wizard_definition["crop"]["y"] + wizard_definition["anchor"][1],
    )
    bundle = {
        "schema_version": 1,
        "canvas": {key: recipe["canvas"][key] for key in ("width", "height")},
        "palette": palette,
        "frames": frame_facts,
        "phases": phases,
        "components": components,
        "cast": {
            "release_frame": release + 1,
            "muzzle": {
                "x": gem.local_position[0] + recipe["gem"]["anchor"][0] - foot[0],
                "y": gem.local_position[1] + recipe["gem"]["anchor"][1] - foot[1],
            },
        },
    }
    write_json(assets / "bundle.json", bundle)
    write_json(
        evidence / "build.json",
        {
            "calls": spa.calls,
            "cli_elapsed_seconds": spa.seconds,
            "recipe_sha256": hashlib.sha256(
                (output / "recipe.json").read_bytes()
            ).hexdigest(),
            "inputs_sha256": hashlib.sha256(
                (evidence / "inputs.json").read_bytes()
            ).hexdigest(),
            "cli": spa.executable,
            "aseprite": spa.aseprite,
        },
    )
    print(
        f"Built {len(sampled)} Frames using {spa.calls} SPA calls in {spa.seconds:.1f}s",
        flush=True,
    )
    return bundle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spa", required=True)
    parser.add_argument("--aseprite", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--recipe", type=Path)
    args = parser.parse_args()
    build(args.spa, args.aseprite, args.output.resolve(), args.recipe)
