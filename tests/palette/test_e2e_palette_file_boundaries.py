"""Native file edge cases that independent decoding alone cannot establish."""

from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.palette_file import decode_palette_file
from tests.palette.support import native_script, palette_fixture, run_palette

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("file_format", ["gpl", "png"])
def test_quantized_gray_export_keeps_native_small_opaque_palette(
    tmp_path, runtime, file_format
):
    source = tmp_path / "source.aseprite"
    native_script(runtime, "quantization.lua", source=source, mode="grayscale")
    original = source.read_bytes()
    destination = tmp_path / f"generated.{file_format}"
    code, result = run_palette(
        "palette",
        "export",
        source_sprite_file=str(source),
        palette_source={
            "kind": "color-quantization",
            "palette_frame_number": 1,
            "max_colors": 8,
            "with_alpha": False,
            "rgb_map_algorithm": "rgb5a3",
            "new_layer_blending_method": True,
        },
        destination={
            "format": file_format,
            "path": str(destination),
            "if_exists": "fail",
        },
    )
    assert code == 0, result
    assert result["quantization"]["actual_colors"] == 5
    decoded = decode_palette_file(destination.read_bytes(), file_format)
    assert len(decoded.entries) == 5 and all(rgba[3] == 255 for rgba in decoded.entries)
    assert source.read_bytes() == original


@pytest.mark.parametrize("transparency", [None, bytes([0])])
def test_png_absent_and_short_transparency_defaults_to_opaque(
    tmp_path, runtime, transparency
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime)
    path = tmp_path / "colors.png"
    image = Image.new("P", (1, 1))
    image.putpalette(bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 40, 50, 60]))
    image.save(path, transparency=transparency)
    code, result = run_palette(
        "palette",
        "import",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        palette_frame_number=3,
        palette_file={"format": "png", "path": str(path)},
    )
    assert code == 0, result
    assert [e["color"]["alpha"] for e in result["palette"]["entries"]] == (
        [255, 255, 255, 255] if transparency is None else [0, 255, 255, 255]
    )


@pytest.mark.parametrize("size", [1, 256, 257])
def test_file_size_boundaries_do_not_implicitly_quantize(
    tmp_path: Path, runtime, size: int
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime, "rgb")
    gpl = tmp_path / "input.gpl"
    gpl.write_text(
        "GIMP Palette\nChannels: RGBA\n"
        + "".join(
            f"{i % 256} {(i * 3) % 256} {(i * 7) % 256} {i % 256} color{i}\n"
            for i in range(size)
        )
    )
    code, result = run_palette(
        "palette",
        "import",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        palette_frame_number=3,
        palette_file={"format": "gpl", "path": str(gpl)},
    )
    assert code == 0, result
    assert len(result["palette"]["entries"]) == size
    stable = target.read_bytes()
    for file_format in ("gpl", "png"):
        destination = tmp_path / f"output.{file_format}"
        destination.write_bytes(b"keep destination")
        code, result = run_palette(
            "palette",
            "export",
            source_sprite_file=str(target),
            palette_source={"kind": "effective", "frame_number": 4},
            destination={
                "format": file_format,
                "path": str(destination),
                "if_exists": "replace",
            },
        )
        if size > 256 and file_format == "png":
            assert code != 0 and result["code"] == "palette_export_rejected", result
            assert result["details"]["palette_size"] == size
            assert destination.read_bytes() == b"keep destination"
        else:
            assert code == 0, result
            assert (
                decode_palette_file(destination.read_bytes(), file_format).entries
                == decode_palette_file(gpl.read_bytes(), "gpl").entries
            )
        assert target.read_bytes() == stable


def test_import_rejects_shrink_that_removes_global_transparent_index(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"keep target")
    gpl = tmp_path / "colors.gpl"
    gpl.write_text("GIMP Palette\n0 0 0 black\n255 255 255 white\n")
    code, result = run_palette(
        "palette",
        "import",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        palette_frame_number=3,
        palette_file={"format": "gpl", "path": str(gpl)},
    )
    assert code != 0 and result["code"] == "palette_transform_rejected", result
    assert result["details"]["reason"] == "transparent_index_removed"
    assert source.read_bytes() == original and target.read_bytes() == b"keep target"


def test_import_checks_unused_tiles_before_publication(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime,
        "index_organization.lua",
        source=source,
        mode="unused-only",
        cross_link="true",
    )
    original = source.read_bytes()
    target.write_bytes(b"keep target")
    gpl = tmp_path / "colors.gpl"
    gpl.write_text("GIMP Palette\n0 0 0 black\n255 255 255 white\n")
    code, result = run_palette(
        "palette",
        "import",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        palette_frame_number=1,
        palette_file={"format": "gpl", "path": str(gpl)},
    )
    assert code != 0 and result["code"] == "palette_transform_rejected", result
    assert result["details"]["reason"] == "index_removed"
    assert result["details"]["tile_uses"][0]["cel_uses"] == []
    assert source.read_bytes() == original and target.read_bytes() == b"keep target"
