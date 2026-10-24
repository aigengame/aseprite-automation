"""Native Palette generation and safe persisted Sprite replacement."""

from pathlib import Path

import pytest

from tests.native_invocation import expect_success, run
from tests.palette.support import quantization_sprite

pytestmark = pytest.mark.e2e


def options(**changes: object) -> dict:
    return dict(
        max_colors=8,
        with_alpha=True,
        rgb_map_algorithm="default",
        new_layer_blending_method=True,
        **changes,
    )


def test_quantization_observes_all_frames_and_actual_size(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    quantization_sprite(runtime, source, mode="rgb")
    original = source.read_bytes()
    result = expect_success(
        "palette color-quantization",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "palette_frame_number": 1,
            **options(),
        },
    )
    facts = result["quantization"]
    assert facts["rendered_frames"] == facts["affected_frames"] == [1, 2]
    assert facts["requested_max_colors"] == 8
    assert facts["actual_colors"] == len(result["palette"]["entries"]) == 5
    assert facts["effective_rgb_map_algorithm"] == "octree"
    colors = {tuple(e["color"].values()) for e in result["palette"]["entries"]}
    assert (255, 0, 0, 255) in colors and (0, 0, 255, 255) in colors
    assert (123, 7, 222, 255) not in colors
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original


def test_quantization_refuses_native_transparency_clamp(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    quantization_sprite(runtime, source, mode="indexed", unsafe="true")
    original = source.read_bytes()
    target.write_bytes(b"keep target")
    outcome = run(
        "palette color-quantization",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            "palette_frame_number": 1,
            "max_colors": 2,
            "with_alpha": True,
            "rgb_map_algorithm": "default",
            "new_layer_blending_method": False,
        },
    )
    result = outcome.envelope
    assert (
        outcome.returncode != 0 and result["code"] == "palette_quantization_rejected"
    ), result
    assert result["details"]["reason"] == "transparent_index_changed"
    assert result["details"]["original_palette_size"] == 8
    assert result["details"]["candidate_palette_size"] == 2
    assert result["details"]["original_transparent_color"] == 7
    assert result["details"]["candidate_transparent_color"] == 1
    assert source.read_bytes() == original and target.read_bytes() == b"keep target"
