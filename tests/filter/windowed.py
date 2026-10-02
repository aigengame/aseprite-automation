"""Explicit local, operator-assisted Tilemap Filter comparison; see docs/testing.md."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from spa.adapters.aseprite.aseprite import probe
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.filter.support import (
    apply,
    native_script,
    observe_images,
    pixels,
    rgb_palette_colors,
)
from tests.filter.test_e2e_filter_tilemaps import PARTIAL_MASK
from tests.filter.test_e2e_tilemap_applications import create, observe

CASES = (
    "rgb",
    "grayscale",
    "indexed",
    "rgb-palette-colors",
    "linked",
    "distinct",
    "spatial",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def observation(runtime, path, mode):
    return {
        "images": observe_images(runtime, path),
        "colors": observe(runtime, path, mode),
    }


def prepare(root, runtime):
    # Refuse reuse: an old UI result or receipt must never satisfy a new run.
    root.mkdir(parents=True, exist_ok=False)
    runner = root / "runner.lua"
    shutil.copyfile(Path(__file__).parent / "fixtures/windowed_filter.lua", runner)
    cases = []
    for name in CASES:
        folder = root / name
        folder.mkdir()
        source, target = folder / "source.aseprite", folder / "spa.aseprite"
        mode = name if name in ("grayscale", "indexed") else "rgb"
        basis, frames = (2, [1]) if name in CASES[:4] else (1, [1, 2])
        palette = name == "rgb-palette-colors"
        # The window's Color Bar picks and Timeline range are alternative sites.
        # Exercise Palette colors at the active Cel, with matching SPA targets.
        if palette:
            frames = [basis]
        selection = {
            "kind": "all",
            "rectangle": {"x": 0, "y": 0, "width": 3, "height": 1},
        }
        if name in CASES[:4]:
            create(runtime, source, mode)
        elif name in ("linked", "distinct"):
            native_script(
                runtime,
                "tilemap_sharing.lua",
                source=source,
                linked=str(name == "linked").lower(),
            )
            selection["rectangle"]["width"] = 1
        else:
            native_script(
                runtime,
                "tilemap_spatial.lua",
                source=source,
                flags=0x20000000,
                offset=-1,
                width=3,
            )
            frames = [1]
            selection = PARTIAL_MASK
        options = {
            "tileset_mode": "manual",
            "channels": {
                "kind": "components",
                "names": ["gray" if mode == "grayscale" else "red"],
            },
            "cels_target": {
                "kind": "selected",
                "layers": [{"layer_path": [1]}],
                "frame_numbers": frames,
            },
            "selection": selection,
        }
        if palette:
            application = rgb_palette_colors(palette_frame_number=basis, **options)
        elif mode == "indexed":
            application = pixels(mode, palette_frame_number=basis, **options)
        else:
            application = pixels(mode, **options)
        source_hash = digest(source)
        before = observation(runtime, source, mode)
        code, result = apply(source, target, application)
        assert code == 0, result
        assert digest(source) == source_hash
        expected = observation(runtime, target, mode)
        assert expected != before, f"{name}: the comparison must detect Cancel/no-op"
        write_json(folder / "spa-result.json", result)
        write_json(folder / "expected.json", expected)
        case = {
            "name": name,
            "mode": mode,
            "basis": basis,
            "frames": frames,
            "palette": palette,
            "selection": selection,
            "channel": "GRAY" if mode == "grayscale" else "RED",
            "source": str(source),
            "target": str(folder / "ui.aseprite"),
            "receipt": str(folder / "ui-receipt.json"),
            "source_sha256": source_hash,
        }
        write_json(folder / "application.json", application)
        # JSON is a Lua string here, never executable source or shell text.
        payload = json.dumps(json.dumps(case))
        (folder / "run.lua").write_text(
            f"dofile({json.dumps(str(runner), ensure_ascii=False)})(json.decode({payload}))\n"
        )
        cases.append(case)
    write_json(
        root / "manifest.json",
        {
            "source_head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "runtime": str(runtime.canonical_path),
            "cases": cases,
        },
    )
    print(
        f"Prepared {len(cases)} cases in {root}. Follow docs/testing.md before verify."
    )


def verify(root, runtime):
    manifest = json.loads((root / "manifest.json").read_text())
    assert tuple(case["name"] for case in manifest["cases"]) == CASES
    report = {"source_head": manifest["source_head"], "cases": []}
    for case in manifest["cases"]:
        folder = root / case["name"]
        assert digest(Path(case["source"])) == case["source_sha256"], case["name"]
        receipt = json.loads(Path(case["receipt"]).read_text())
        assert receipt["name"] == case["name"]
        assert receipt["is_ui_available"] is True and receipt["reopened"] is True
        assert receipt["tileset_mode"] == "manual"
        assert receipt["active_frame"] == case["basis"]
        assert receipt["frames"] == case["frames"]
        assert receipt["colors"] == ([1] if case["palette"] else [])
        assert receipt["selection_pixels"] == (
            3 if case["name"] == "spatial" else case["selection"]["rectangle"]["width"]
        )
        actual = observation(runtime, Path(case["target"]), case["mode"])
        expected = json.loads((folder / "expected.json").read_text())
        write_json(folder / "actual.json", actual)
        assert actual == expected, (
            f"{case['name']}: reopened UI output differs from SPA"
        )
        report["cases"].append(
            {"name": case["name"], "version": receipt["version"], "matches_spa": True}
        )
        print(f"PASS {case['name']}: UI save/reopen matches SPA")
    write_json(root / "comparison.json", report)
    print(
        "Retain dialog screenshots/operator observations with this report; receipts alone do not prove UI actions."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    runtime = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    {"prepare": prepare, "verify": verify}[args.action](
        args.directory.resolve(), runtime
    )


if __name__ == "__main__":
    main()
