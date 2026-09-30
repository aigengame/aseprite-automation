"""Real-runtime Image fixtures and independent native/export observations."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import process_diagnostics, spa


def image_fixture(tmp_path: Path, mode: str = "rgb") -> Path:
    source = tmp_path / "source.aseprite"
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    with tempfile.TemporaryDirectory(prefix="spa-image-fixture-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={source}",
                "--script-param",
                f"mode={mode}",
                "--script",
                str(Path(__file__).parent / "fixtures" / "resize_targets.lua"),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, process_diagnostics(run)
    assert source.is_file()
    return source


def export_image(source: Path, output: Path, frame_number: int = 1) -> Image.Image:
    run = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(
            {
                "source_sprite_file": str(source),
                "destination": {"path": str(output), "if_exists": "fail"},
                "frame_number": frame_number,
                "color_mode": "preserve",
                "color_profile": "preserve",
                "transparency": "preserve",
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    with Image.open(output) as image:
        image.load()
        return image.convert("RGBA")


def inspect_native(
    source: Path,
    tmp_path: Path,
    x: int,
    y: int,
    frame_number: int = 1,
    *,
    row: bool = False,
) -> dict:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    output = tmp_path / f"pixel-{frame_number}-{x}-{y}.json"
    with tempfile.TemporaryDirectory(prefix="spa-image-inspect-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        arguments = [str(prepared.executable), "--batch"]
        for key, value in {
            "source": source,
            "frame": frame_number,
            "x": x,
            "y": y,
            "out": output,
            "row": "true" if row else "false",
        }.items():
            arguments.extend(("--script-param", f"{key}={value}"))
        arguments.extend(
            ("--script", str(Path(__file__).parent / "fixtures" / "inspect_image.lua"))
        )
        run = subprocess.run(
            arguments,
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, process_diagnostics(run)
    return json.loads(output.read_text())
