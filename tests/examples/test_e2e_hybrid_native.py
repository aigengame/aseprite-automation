"""Native comparison must inspect stored pixels that delivery PNGs cannot show."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from examples.wizard_cast_v2.native_inspection import compare_native
from examples.wizard_cast_v2.probe import build_probe
from examples.wizard_cast_v2.workflow import Spa, paint_steps

pytestmark = pytest.mark.e2e


def test_native_comparison_detects_hidden_pixels_with_unchanged_exports(
    tmp_path: Path,
) -> None:
    executable = os.environ.get(
        "SPA_TEST_INSTALLED_CLI", str(Path(".venv/bin/spa").resolve())
    )
    aseprite = os.environ["SPA_TEST_ASEPRITE"]
    build_probe(executable, aseprite, tmp_path / "probe")
    original = tmp_path / "probe/handoff.aseprite"
    changed = tmp_path / "changed.aseprite"
    spa = Spa(executable, aseprite, tmp_path / "operations.jsonl")
    # Derived native components retain hidden Layers. A hidden Layer contributes
    # no rendered RGBA, including RGB under zero alpha, so all exports can agree
    # while a stored Cel differs. Frame 3 also has explicit zero Cel opacity.
    spa.mutate(
        "layer set",
        original,
        target={"layer_path": [1]},
        properties={"is_visible": False},
    )
    spa.call(
        "sprite copy",
        source_sprite_file=str(original),
        target_sprite_file=str(changed),
        overwrite=False,
    )
    preparation = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "examples/wizard_cast_v2/inputs/preparation.json"
        ).read_text()
    )
    palette = {color.lower() for color in preparation["palette"].values()}
    compare_native(original, changed, spa, tmp_path, palette)
    with Image.open(tmp_path / "probe/frame-1.png") as image:
        width, height = image.size
    # Image-pixel (0,0) is in the prepared raster's transparent padding. Writing
    # a declared opaque color changes its hidden content without changing bounds.
    spa.plan(
        changed,
        paint_steps(
            1, 3, width - 4, height - 4, {(0, 0): preparation["palette"]["gold"]}
        ),
    )
    for frame in range(1, 4):
        before = tmp_path / f"before-{frame}.png"
        after = tmp_path / f"after-{frame}.png"
        spa.export(original, frame, before)
        spa.export(changed, frame, after)
        with Image.open(before) as left, Image.open(after) as right:
            assert left.convert("RGBA").tobytes() == right.convert("RGBA").tobytes()
    with pytest.raises(AssertionError, match="stored RGBA pixels differ"):
        compare_native(original, changed, spa, tmp_path, palette)
