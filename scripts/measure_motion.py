"""One-off local issue #104 motion timing; writes all generated data outside the repo.

Run from a checkout with SPA_TEST_ASEPRITE set and spa on PATH:
    python -m scripts.measure_motion --output /tmp/spa-motion-measurement
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from fractions import Fraction
from pathlib import Path

from tests.motion.test_e2e_motion import fixture, inspect


def cli(group: str, action: str, request: dict) -> tuple[float, dict]:
    started = time.perf_counter()
    completed = subprocess.run(
        ["spa", group, action, "--input-json", json.dumps(request)],
        capture_output=True,
        text=True,
        check=False,
    )
    duration = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(f"{group} {action}: {completed.stdout}\n{completed.stderr}")
    response = json.loads(completed.stdout)
    return duration, response


def near_away(value: Fraction) -> int:
    magnitude = math.floor(abs(value) + Fraction(1, 2))
    return magnitude if value >= 0 else -magnitude


def motion_input(frame_count: int) -> dict:
    return {
        "layer": {"layer_path": [1]},
        "from_frame": 1,
        "to_frame": frame_count,
        "position_offsets": {
            "interpolation": "linear",
            "rounding": "nearest-away-from-zero",
            "keys": [
                {"frame_number": 1, "offset": {"x": 0, "y": 0}},
                {"frame_number": frame_count, "offset": {"x": 2, "y": -2}},
            ],
        },
        "opacity": {
            "interpolation": "linear",
            "rounding": "floor",
            "keys": [
                {"frame_number": 1, "opacity": 0},
                {"frame_number": frame_count, "opacity": 255},
            ],
        },
    }


def run_case(
    kind: str, source: Path, folder: Path, sequence: int, frame_count: int
) -> dict:
    binary = os.environ["SPA_TEST_ASEPRITE"]
    cases = {}
    for mode in ("cel", "motion", "plan"):
        target = folder / f"{kind}-{sequence}-{mode}.aseprite"
        shutil.copyfile(source, target)
        durations = []
        if mode == "cel":
            for frame_number in range(1, frame_count + 1):
                t = Fraction(frame_number - 1, frame_count - 1)
                dx, dy = near_away(2 * t), near_away(-2 * t)
                request = {
                    "aseprite": binary,
                    "source_sprite_file": str(target),
                    "target_sprite_file": str(target),
                    "in_place": True,
                    "overwrite": True,
                    "target": {
                        "layer": {"layer_path": [1]},
                        "frame_number": frame_number,
                    },
                    "position": {
                        "x": frame_number - 3 + dx,
                        "y": 3 - frame_number + dy,
                    },
                    "opacity": math.floor(255 * t),
                }
                elapsed, result = cli("cel", "set", request)
                assert result["persisted_reopen_verified"] is True
                durations.append(elapsed)
        else:
            request = {
                "aseprite": binary,
                "source_sprite_file": str(target),
                "target_sprite_file": str(target),
                "in_place": True,
                "overwrite": True,
            }
            if mode == "motion":
                elapsed, result = cli(
                    "motion", "apply", request | motion_input(frame_count)
                )
                assert result["persisted_reopen_verified"] is True
            else:
                elapsed, result = cli(
                    "plan",
                    "run",
                    {
                        "aseprite": binary,
                        "plan": {
                            "source_sprite_file": str(target),
                            "target_sprite_file": str(target),
                            "in_place": True,
                            "overwrite": True,
                            "steps": [
                                {
                                    "operation": "motion apply",
                                    "input": motion_input(frame_count),
                                }
                            ],
                        },
                    },
                )
                assert result["persisted_reopen_verified"] is True
                assert (
                    result["steps"][0]["result"]["persisted_reopen_verified"] is False
                )
            durations.append(elapsed)
        cases[mode] = {
            "seconds": sum(durations),
            "call_seconds": durations,
            "calls": len(durations),
            "file": target,
        }
    # Native inspect is outside timed regions and opens persisted outputs.
    original = inspect(source, folder)
    states = {mode: inspect(data["file"], folder) for mode, data in cases.items()}
    assert states["cel"] == states["motion"] == states["plan"], (
        "persisted native states differ"
    )
    after = states["motion"]
    assert original["frames"] == after["frames"]
    assert len(original["cels"]) == len(after["cels"])
    for before, updated in zip(original["cels"], after["cels"], strict=True):
        for field in ("pixels", "width", "height", "z", "links", "frame", "layer"):
            assert updated[field] == before[field], field
        if before["layer"] == "untouched":
            assert updated == before
    for data in cases.values():
        data["sha256"] = hashlib.sha256(data.pop("file").read_bytes()).hexdigest()
    return {
        "subject": kind,
        "sequence": sequence,
        "warmup": sequence == 0,
        "cases": cases,
        "native_cels_verified": len(after["cels"]),
        "native_facts_equal": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, choices=(5, 32), default=5)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source_files = {}
    for kind in ("wizard", "emblem"):
        folder = args.output / kind
        folder.mkdir(exist_ok=True)
        source = fixture(folder, frame_count=args.frames, artwork=kind)
        source_files[kind] = {
            "file": str(source),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "bytes": source.stat().st_size,
        }
    rows = []
    for sequence in range(4):
        for kind in ("wizard", "emblem"):
            row = run_case(
                kind,
                Path(source_files[kind]["file"]),
                args.output / kind,
                sequence,
                args.frames,
            )
            rows.append(row)
            (args.output / "raw.json").write_text(
                json.dumps(
                    {"source_files": source_files, "frames": args.frames, "runs": rows},
                    indent=2,
                )
            )
            print(
                kind,
                sequence,
                {k: round(v["seconds"], 3) for k, v in row["cases"].items()},
                flush=True,
            )
    for source in source_files.values():
        assert (
            hashlib.sha256(Path(source["file"]).read_bytes()).hexdigest()
            == source["sha256"]
        )
    print("Complete: 3 measured runs per subject after one warmup", flush=True)


if __name__ == "__main__":
    main()
