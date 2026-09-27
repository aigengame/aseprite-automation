"""Small example-owned adapter to the installed public SPA CLI."""

import json
import subprocess
import time
from pathlib import Path


class Spa:
    def __init__(self, executable: str, aseprite: str, evidence: Path) -> None:
        self.executable = str(Path(executable).resolve())
        self.aseprite = str(Path(aseprite).expanduser().resolve())
        self.evidence = evidence
        self.calls = 0
        self.seconds = 0.0

    def call(self, operation: str, **request: object) -> dict:
        request = {"aseprite": self.aseprite, **request}
        started = time.monotonic()
        process = subprocess.run(
            [self.executable, *operation.split(), "--input-json", "-"],
            input=json.dumps(request),
            text=True,
            capture_output=True,
            check=False,
        )
        elapsed = time.monotonic() - started
        try:
            result = json.loads(process.stdout)
        except ValueError as error:
            raise RuntimeError(
                f"{operation}: invalid CLI output: {process.stderr}"
            ) from error
        self.calls += 1
        self.seconds += elapsed
        with self.evidence.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "operation": operation,
                        "request": request,
                        "elapsed_seconds": elapsed,
                        "returncode": process.returncode,
                        "result": result,
                    }
                )
                + "\n"
            )
        if process.returncode or result.get("status") != "success":
            raise RuntimeError(f"{operation}: {json.dumps(result)}")
        return result

    def mutate(self, operation: str, source: Path, **request: object) -> dict:
        return self.call(
            operation,
            source_sprite_file=str(source),
            target_sprite_file=str(source),
            in_place=True,
            overwrite=True,
            **request,
        )

    def plan(self, source: Path, steps: list[dict]) -> dict:
        return self.call(
            "plan run",
            plan={
                "source_sprite_file": str(source),
                "target_sprite_file": str(source),
                "in_place": True,
                "overwrite": True,
                "steps": steps,
            },
        )

    def export(self, source: Path, frame: int, destination: Path) -> dict:
        destination.parent.mkdir(parents=True, exist_ok=True)
        return self.call(
            "export image",
            source_sprite_file=str(source),
            frame_number=frame,
            destination={"path": str(destination), "if_exists": "fail"},
            color_mode="preserve",
            color_profile="preserve",
            transparency="preserve",
        )


def target(layer: int, frame: int) -> dict:
    return {"layer": {"layer_path": [layer]}, "frame_number": frame}


def rgba(hex_color: str | None) -> dict:
    if hex_color is None:
        values = (0, 0, 0, 0)
    else:
        code = hex_color.removeprefix("#")
        values = (*[int(code[i : i + 2], 16) for i in (0, 2, 4)], 255)
    return dict(zip(("red", "green", "blue", "alpha"), values), kind="rgba")


def paint_steps(
    layer: int,
    frame: int,
    width: int,
    height: int,
    pixels: dict[tuple[int, int], str | None],
) -> list[dict]:
    """Turn finite pixel inputs into canonical, bounded public Pixel Patches."""
    runs: list[dict] = []
    for (x, y), color in sorted(
        pixels.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"Pixel {(x, y)} outside {width}×{height}")
        value = rgba(color)
        if (
            runs
            and runs[-1]["y"] == y
            and runs[-1]["x"] + runs[-1]["length"] == x
            and runs[-1]["color"] == value
        ):
            runs[-1]["length"] += 1
        else:
            runs.append({"x": x, "y": y, "length": 1, "color": value})
    batches: list[list[dict]] = []
    current: list[dict] = []
    count = 0
    for run in runs:
        remaining = run["length"]
        x = run["x"]
        while remaining:
            take = min(remaining, 256 - count)
            current.append({**run, "x": x, "length": take})
            count += take
            x += take
            remaining -= take
            if count == 256:
                batches.append(current)
                current, count = [], 0
    if current:
        batches.append(current)
    return [
        {
            "operation": "paint apply",
            "input": {
                "target": {"layer_path": [layer], "frame_number": frame},
                "patch": {
                    "coordinate_space": "image-pixel",
                    "rectangle": {"x": 0, "y": 0, "width": width, "height": height},
                    "runs": batch,
                },
            },
        }
        for batch in batches
    ]
