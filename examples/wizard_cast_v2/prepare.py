"""Reproduce the declared, finite preparation of selected imagegen inputs."""

import argparse
import hashlib
import json
from functools import cache
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(definition: dict, palette: dict[str, str]) -> dict:
    source = ROOT / "inputs" / definition["raw"]
    destination = ROOT / "inputs" / definition["prepared"]
    with Image.open(source) as opened:
        raw = opened.convert("RGBA")
    original_alpha = raw.getchannel("A")
    threshold = definition.get("alpha_threshold", 128)
    raw.putalpha(original_alpha.point(lambda value: 255 if value >= threshold else 0))
    bounds = definition.get("crop") or raw.getbbox()
    if bounds is None:
        raise ValueError(f"Empty selected input: {source}")
    cropped = raw.crop(tuple(bounds))
    fit = definition["fit"]
    if "scale" in definition:
        factor = definition["scale"]
        fit = [round(cropped.width * factor), round(cropped.height * factor)]
    elif definition.get("preserve_aspect", True):
        factor = min(fit[0] / cropped.width, fit[1] / cropped.height)
        fit = [round(cropped.width * factor), round(cropped.height * factor)]
    resized = cropped.resize(tuple(fit), Image.Resampling.NEAREST)
    colors = [tuple(bytes.fromhex(value[1:])) for value in palette.values()]

    @cache
    def nearest(rgb: tuple) -> tuple:
        return min(
            colors, key=lambda color: sum((a - b) ** 2 for a, b in zip(rgb, color))
        )

    data = []
    for rgba in resized.get_flattened_data():
        data.append((*nearest(rgba[:3]), 255) if rgba[3] else (0, 0, 0, 0))
    resized.putdata(data)
    prepared = Image.new("RGBA", tuple(definition["canvas"]))
    offset = definition["offset"]
    if "raw_anchor" in definition:
        offset = [
            definition["anchor"][axis]
            - round(
                (definition["raw_anchor"][axis] - bounds[axis]) * definition["scale"]
            )
            for axis in (0, 1)
        ]
    if min(offset) < 0 or any(offset[i] + fit[i] > prepared.size[i] for i in (0, 1)):
        raise ValueError(f"Prepared asset does not fit its declared canvas: {source}")
    prepared.paste(resized, tuple(offset))
    destination.parent.mkdir(parents=True, exist_ok=True)
    prepared.save(destination)
    return {
        "raw": definition["raw"],
        "prepared": definition["prepared"],
        "raw_sha256": digest(source),
        "prepared_sha256": digest(destination),
        "raw_size": list(raw.size),
        "raw_alpha_values": len(set(original_alpha.get_flattened_data())),
        "alpha_threshold": threshold,
        "crop": list(bounds),
        "resized_size": fit,
        "canvas": list(prepared.size),
        "offset": offset,
        "resampling": "nearest-neighbor",
        "color_mapping": "minimum squared RGB distance, declared palette order breaks ties",
        "dithering": False,
        "visible_pixels": sum(
            value != 0 for value in prepared.getchannel("A").get_flattened_data()
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=ROOT / "inputs/preparation.json")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    report = [prepare(definition, spec["palette"]) for definition in spec["assets"]]
    (ROOT / "inputs/preparation-evidence.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
