"""Canonical Image snapshots through the public CLI and real native files."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _fixture(tmp_path: Path, mode: str = "rgb") -> Path:
    source = tmp_path / f"{mode}.aseprite"
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    with tempfile.TemporaryDirectory(prefix="spa-snapshot-fixture-") as work:
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
                str(Path(__file__).parent / "fixtures" / "snapshot_targets.lua"),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr
    return source


def _get(source: Path, **options: object) -> tuple[int, dict]:
    run = spa(
        "image",
        "get",
        "--input-json",
        json.dumps(
            {
                "sprite_file": str(source),
                "source": {
                    "kind": "individual",
                    "target": {
                        "layer": {"layer_path": [1]},
                        "frame_number": 1,
                    },
                    "rectangle": {"x": 1, "y": 1, "width": 2, "height": 1},
                },
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                **options,
            }
        ),
    )
    return run.returncode, json.loads(run.stdout)


def test_individual_get_reads_hidden_stored_pixels_and_rebases_roi(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path)
    original = source.read_bytes()

    code, result = _get(source)

    assert code == 0, result
    assert result["source"]["coordinate_space"] == "image-pixel"
    assert result["source"]["rectangle"] == {"x": 1, "y": 1, "width": 2, "height": 1}
    assert result["snapshot"] == {
        "coordinate_space": "image-pixel",
        "color_mode": "rgb",
        "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
        "rows": [
            [
                {
                    "length": 1,
                    "color": {
                        "kind": "rgba",
                        "red": 70,
                        "green": 80,
                        "blue": 90,
                        "alpha": 0,
                    },
                },
                {
                    "length": 1,
                    "color": {
                        "kind": "rgba",
                        "red": 3,
                        "green": 4,
                        "blue": 5,
                        "alpha": 128,
                    },
                },
            ]
        ],
    }
    assert result["source"]["layer_kind"] == "transparent"
    assert result["source"]["associated_cels"][0]["opacity"] == 0
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("mode", "colors", "mask"),
    [
        (
            "grayscale",
            [
                {"kind": "grayscale", "gray": 72, "alpha": 0},
                {"kind": "grayscale", "gray": 9, "alpha": 128},
            ],
            {"kind": "grayscale", "gray": 0, "alpha": 0},
        ),
        (
            "indexed",
            [
                {"kind": "palette-index", "index": 0},
                {"kind": "palette-index", "index": 2},
            ],
            {"kind": "palette-index", "index": 2},
        ),
    ],
)
def test_native_modes_preserve_stored_values_and_palette_basis(
    tmp_path: Path,
    mode: str,
    colors: list[dict],
    mask: dict,
) -> None:
    source = _fixture(tmp_path, mode)
    code, result = _get(source)
    assert code == 0, result
    assert result["snapshot"]["color_mode"] == mode
    assert [run["color"] for run in result["snapshot"]["rows"][0]] == colors
    assert result["mask_color"] == mask
    palettes = result["effective_palettes"]
    if mode == "indexed":
        assert palettes == [
            {
                "frame_number": 1,
                "palette_frame_number": 1,
                "palette_size": 4,
                "indexes": [
                    {
                        "index": 0,
                        "color": {"red": 30, "green": 40, "blue": 50, "alpha": 255},
                    },
                    {
                        "index": 2,
                        "color": {"red": 0, "green": 0, "blue": 250, "alpha": 255},
                    },
                ],
            }
        ]
    else:
        assert palettes == []
