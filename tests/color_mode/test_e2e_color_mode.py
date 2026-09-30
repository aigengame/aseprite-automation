"""Native Color Mode conversions through the installed SPA surface."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e


def run(*command: str, **request: object) -> tuple[int, dict]:
    result = spa(
        *command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


def make_source(source: Path, runtime, mode: str = "rgb") -> None:
    with tempfile.TemporaryDirectory(prefix="spa-color-mode-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        result = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"source={source}",
                "--script-param",
                f"mode={mode}",
                "--script",
                str(Path(__file__).parent / "fixtures" / "source.lua"),
            ],
            env=prepared.environment,
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 0, process_diagnostics(result)


def convert(source: Path, target: Path, conversion: dict) -> tuple[int, dict]:
    return run(
        "sprite",
        "change-color-mode",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        conversion=conversion,
    )


def test_rgb_to_grayscale_preserves_source_and_reports_reopened_images(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime)
    original = source.read_bytes()
    code, result = convert(
        source,
        target,
        {
            "source_color_mode": "rgb",
            "target": {"color_mode": "grayscale", "to_gray": "luma"},
        },
    )
    assert code == 0, result
    assert result["source_color_mode"] == "rgb"
    assert result["target_color_mode"] == "grayscale"
    assert result["changed"] is True
    assert result["persisted_reopen_verified"] is True
    assert result["before"]["images"][0]["bytes_per_pixel"] == 4
    assert result["after"]["images"][0]["bytes_per_pixel"] == 2
    assert (
        result["before"]["images"][0]["content"]
        != result["after"]["images"][0]["content"]
    )
    code, inspected = run(
        "sprite", "get", sprite_file=str(target), inspection_scope=["cels", "palettes"]
    )
    assert code == 0, inspected
    assert inspected["metadata"]["color_mode"] == "grayscale"
    assert source.read_bytes() == original


def conversion_for(source: str, target: str) -> dict:
    options: dict = {"color_mode": target}
    if source != target:
        if target == "grayscale":
            options["to_gray"] = "luma"
        if target == "indexed":
            options.update(
                rgb_map_algorithm="default", color_best_fit_criteria="default"
            )
            if source == "rgb":
                options["dithering"] = {"algorithm": "none"}
    return {"source_color_mode": source, "target": options}


@pytest.mark.parametrize("source_mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("target_mode", ["rgb", "grayscale", "indexed"])
def test_every_color_mode_pair(tmp_path, runtime, source_mode, target_mode):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime, source_mode)
    original = source.read_bytes()
    code, result = convert(source, target, conversion_for(source_mode, target_mode))
    assert code == 0, result
    assert result["after"]["color_mode"] == target_mode
    assert result["changed"] == (source_mode != target_mode)
    if source_mode == target_mode:
        assert result["before"] == result["after"]
        assert result["mapping"] is None and result["dithering"] is None
    elif target_mode == "indexed":
        assert result["mapping"] == {
            "requested_rgb_map_algorithm": "default",
            "effective_rgb_map_algorithm": "octree",
            "color_best_fit_criteria": "default",
        }
        assert (
            sum(
                item["pixel_count"]
                for item in result["after"]["images"][0]["palette_indices"]
            )
            == 3
        )
        if source_mode == "rgb":
            assert result["dithering"]["effective_algorithm"] == "none"
        else:
            assert result["dithering"] is None
    assert source.read_bytes() == original
