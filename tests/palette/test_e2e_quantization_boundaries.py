"""Quantization options, exact change scope, and Indexed publication boundaries."""

import json
from pathlib import Path

import pytest

from tests.palette.support import native_script, run_palette
from tests.support import inject_palette_change

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize(
    "mode,algorithm,alpha,blend",
    [
        ("rgb", "rgb5a3", False, False),
        ("rgb", "octree", True, False),
        ("grayscale", "octree", True, False),
        ("grayscale", "rgb5a3", True, True),
        ("indexed", "default", True, False),
        ("indexed", "octree", False, True),
    ],
)
def test_explicit_quantization_variants_repeat_deterministically(
    tmp_path: Path, runtime, mode, algorithm, alpha, blend
) -> None:
    source = tmp_path / "source.aseprite"
    native_script(runtime, "quantization.lua", source=source, mode=mode)
    original = source.read_bytes()
    observations = []
    for repeat in range(2):
        code, result = run_palette(
            "palette",
            "color-quantization",
            source_sprite_file=str(source),
            target_sprite_file=str(tmp_path / f"out{repeat}.aseprite"),
            in_place=False,
            overwrite=False,
            palette_frame_number=1,
            max_colors=8,
            with_alpha=alpha,
            rgb_map_algorithm=algorithm,
            new_layer_blending_method=blend,
        )
        assert code == 0, json.dumps(result)
        assert result["quantization"]["with_alpha"] is alpha
        assert result["quantization"]["new_layer_blending_method"] is blend
        assert result["quantization"]["rgb_map_algorithm"] == algorithm
        if mode == "indexed":
            assert result["quantization"]["original_transparent_color"] == 0
            assert result["quantization"]["final_transparent_color"] == 0
        if alpha and mode != "indexed":
            assert any(
                0 < e["color"]["alpha"] < 255 for e in result["palette"]["entries"]
            )
        if not alpha:
            assert all(
                e["color"]["alpha"] in (0, 255) for e in result["palette"]["entries"]
            )
        observations.append((result["palette_changes"], result["quantization"]))
    assert observations[0] == observations[1]
    assert source.read_bytes() == original


@pytest.mark.parametrize("maximum", [1, 256])
def test_quantization_size_limits(tmp_path: Path, runtime, maximum: int) -> None:
    source = tmp_path / "source.aseprite"
    native_script(runtime, "quantization.lua", source=source, mode="rgb")
    code, result = run_palette(
        "palette",
        "color-quantization",
        source_sprite_file=str(source),
        target_sprite_file=str(tmp_path / "out.aseprite"),
        in_place=False,
        overwrite=False,
        palette_frame_number=1,
        max_colors=maximum,
        with_alpha=True,
        rgb_map_algorithm="rgb5a3",
        new_layer_blending_method=True,
    )
    assert code == 0, json.dumps(result)
    assert 1 <= result["quantization"]["actual_colors"] <= maximum


def test_quantization_changes_one_palette_but_renders_all_frames(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "source.aseprite"
    native_script(runtime, "quantization.lua", source=source, mode="rgb")
    inject_palette_change(source, [(1, 2, 3, 255), (3, 4, 5, 128)], frame_number=2)
    code, before = run_palette("palette", "list", sprite_file=str(source))
    assert code == 0, before
    code, result = run_palette(
        "palette",
        "color-quantization",
        source_sprite_file=str(source),
        target_sprite_file=str(tmp_path / "out.aseprite"),
        in_place=False,
        overwrite=False,
        palette_frame_number=2,
        max_colors=8,
        with_alpha=True,
        rgb_map_algorithm="default",
        new_layer_blending_method=True,
    )
    assert code == 0, json.dumps(result)
    assert result["palette_changes"][0] == before["palette_changes"][0]
    assert result["palette"]["palette_frame_number"] == 2
    assert result["quantization"]["rendered_frames"] == [1, 2]
    assert result["quantization"]["affected_frames"] == [2]
    assert len(result["palette"]["entries"]) == 5


@pytest.mark.parametrize("algorithm", ["default", "octree"])
@pytest.mark.parametrize("export", [False, True])
def test_native_color_limit_overrun_refuses_sprite_and_palette_publication(
    tmp_path, runtime, algorithm, export
):
    source = tmp_path / "source.aseprite"
    native_script(runtime, "quantization.lua", source=source, mode="rgb")
    original = source.read_bytes()
    target = tmp_path / ("palette.gpl" if export else "target.aseprite")
    target.write_bytes(b"keep target")
    options = {
        "palette_frame_number": 1,
        "max_colors": 1,
        "with_alpha": True,
        "rgb_map_algorithm": algorithm,
        "new_layer_blending_method": True,
    }
    if export:
        code, result = run_palette(
            "palette",
            "export",
            source_sprite_file=str(source),
            palette_source={"kind": "color-quantization", **options},
            destination={"format": "gpl", "path": str(target), "if_exists": "replace"},
        )
    else:
        code, result = run_palette(
            "palette",
            "color-quantization",
            source_sprite_file=str(source),
            target_sprite_file=str(target),
            in_place=False,
            overwrite=True,
            **options,
        )
    assert code != 0 and result["code"] == "palette_quantization_rejected", result
    assert result["details"]["reason"] == "color_limit_exceeded"
    assert result["details"]["requested_max_colors"] == 1
    assert result["details"]["candidate_palette_size"] == 3
    assert source.read_bytes() == original and target.read_bytes() == b"keep target"


@pytest.mark.parametrize("operation", ["import", "color-quantization"])
def test_native_grayscale_palette_expansion_refuses_sprite_publication(
    tmp_path, runtime, operation
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "quantization.lua", source=source, mode="grayscale")
    original = source.read_bytes()
    target.write_bytes(b"keep target")
    if operation == "import":
        palette = tmp_path / "colors.gpl"
        palette.write_text(
            "GIMP Palette\n"
            + "".join(
                f"{gray} {gray} {gray} gray{gray}\n" for gray in [0, 20, 70, 160, 240]
            )
        )
        options = {"palette_file": {"format": "gpl", "path": str(palette)}}
    else:
        options = {
            "max_colors": 8,
            "with_alpha": False,
            "rgb_map_algorithm": "rgb5a3",
            "new_layer_blending_method": True,
        }
    code, result = run_palette(
        "palette",
        operation,
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        palette_frame_number=1,
        **options,
    )
    assert code != 0 and result["code"] == "palette_persistence_failed", result
    assert result["details"]["expected_palette_size"] == 5
    assert result["details"]["reopened_palette_size"] == 256
    assert source.read_bytes() == original and target.read_bytes() == b"keep target"


@pytest.mark.parametrize("maximum,target_kind", [(1, "cel_uses"), (2, "tile_uses")])
def test_invalid_linked_or_unused_tile_indexes_refuse_publication(
    tmp_path: Path, runtime, maximum: int, target_kind: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime,
        "index_organization.lua",
        source=source,
        mode="linked-only" if maximum == 1 else "unused-only",
        cross_link="true",
    )
    original = source.read_bytes()
    target.write_bytes(b"keep target")
    code, result = run_palette(
        "palette",
        "color-quantization",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        palette_frame_number=1,
        max_colors=maximum,
        with_alpha=True,
        rgb_map_algorithm="rgb5a3" if maximum == 1 else "octree",
        new_layer_blending_method=True,
    )
    assert code != 0 and result["code"] == "palette_quantization_rejected", json.dumps(
        result
    )
    assert result["details"]["reason"] == "index_out_of_bounds"
    assert result["details"][target_kind]
    if target_kind == "cel_uses":
        assert len(result["details"]["cel_uses"]) == 4
    else:
        assert result["details"]["tile_uses"][0]["cel_uses"] == []
    assert source.read_bytes() == original and target.read_bytes() == b"keep target"


def test_export_generates_palette_without_publishing_unsafe_indexed_sprite(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "source.aseprite"
    native_script(
        runtime, "quantization.lua", source=source, mode="indexed", unsafe="true"
    )
    original = source.read_bytes()
    code, result = run_palette(
        "palette",
        "export",
        source_sprite_file=str(source),
        palette_source={
            "kind": "color-quantization",
            "palette_frame_number": 1,
            "max_colors": 2,
            "with_alpha": True,
            "rgb_map_algorithm": "default",
            "new_layer_blending_method": False,
        },
        destination={
            "format": "png",
            "path": str(tmp_path / "palette.png"),
            "if_exists": "fail",
        },
    )
    assert code == 0, json.dumps(result)
    assert result["quantization"]["actual_colors"] == 2
    assert result["quantization"]["original_transparent_color"] == 7
    assert result["quantization"]["final_transparent_color"] == 1
    assert result["artifact"]["role"] == "palette"
    assert source.read_bytes() == original
