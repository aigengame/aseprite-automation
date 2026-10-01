"""Palette files preserve ordered colors through the public SPA operations."""

from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.palette_file import decode_palette_file
from tests.palette.support import palette_fixture, run_palette

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("file_format", ["gpl", "png"])
@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_import_replaces_one_change_and_preserves_source(
    tmp_path: Path, runtime, file_format: str, mode: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime, mode)
    original = source.read_bytes()
    palette_file = tmp_path / f"colors.{file_format}"
    if file_format == "gpl":
        palette_file.write_text(
            "GIMP Palette\nChannels: RGBA\nName: fixture\n#\n"
            "11 22 33 0 transparent\n44 55 66 128 partial\n"
            "77 88 99 255 opaque\n44 55 66 128 duplicate\n"
        )
    else:
        card = Image.new("P", (1, 1))  # Three Entries deliberately have no pixel use.
        card.putpalette(bytes([11, 22, 33, 44, 55, 66, 77, 88, 99, 44, 55, 66]))
        card.save(palette_file, transparency=bytes([0, 128, 255, 128]))
    code, before = run_palette("palette", "list", sprite_file=str(source))
    assert code == 0, before
    code, result = run_palette(
        "palette",
        "import",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        palette_frame_number=3,
        palette_file={"format": file_format, "path": str(palette_file)},
    )
    assert code == 0, result
    expected = [
        {"index": index, "color": dict(zip(("red", "green", "blue", "alpha"), rgba))}
        for index, rgba in enumerate(
            [(11, 22, 33, 0), (44, 55, 66, 128), (77, 88, 99, 255), (44, 55, 66, 128)]
        )
    ]
    code, after = run_palette("palette", "list", sprite_file=str(target))
    assert code == 0, after
    before["palette_changes"][1]["entries"] = expected
    assert after["palette_changes"] == before["palette_changes"]
    assert result["palette"]["entries"] == expected
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original


@pytest.mark.parametrize("frame", [2, 100, 2**53 + 1])
def test_import_requires_an_exact_change(tmp_path: Path, runtime, frame: int) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"keep target")
    colors = tmp_path / "colors.gpl"
    colors.write_text("GIMP Palette\n0 0 0 black\n1 2 3 dark\n4 5 6 gray\n7 8 9 pale\n")
    code, result = run_palette(
        "palette",
        "import",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        palette_frame_number=frame,
        palette_file={"format": "gpl", "path": str(colors)},
    )
    assert code != 0 and result["code"] == "palette_change_missing", result
    assert result["details"]["palette_frame_number"] == frame
    assert source.read_bytes() == original and target.read_bytes() == b"keep target"


@pytest.mark.parametrize("file_format", ["gpl", "png"])
@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_export_effective_palette_preserves_all_entries_and_source(
    tmp_path: Path, runtime, mode: str, file_format: str
) -> None:
    source = tmp_path / "source.aseprite"
    palette_fixture(source, runtime, mode)
    original = source.read_bytes()
    destination = tmp_path / f"colors.{file_format}"
    code, selected = run_palette(
        "palette", "get", sprite_file=str(source), frame_number=4
    )
    assert code == 0, selected
    code, result = run_palette(
        "palette",
        "export",
        source_sprite_file=str(source),
        palette_source={"kind": "effective", "frame_number": 4},
        destination={
            "format": file_format,
            "path": str(destination),
            "if_exists": "fail",
        },
    )
    assert code == 0, result
    assert result["palette"] == selected["palette"]
    assert result["palette"]["palette_frame_number"] == 3
    assert result["artifact"]["role"] == "palette"
    assert result["artifact"]["byte_size"] == destination.stat().st_size
    decoded = decode_palette_file(destination.read_bytes(), file_format)
    expected = tuple(tuple(e["color"].values()) for e in selected["palette"]["entries"])
    assert decoded.entries == expected
    assert result["artifact"]["sha256"] == decoded.sha256
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "record, failure",
    [
        ("256 0 0 wrong", "palette_file_failed"),
        ("0 0 0", "palette_file_failed"),  # Native GPL omits unnamed sole record.
        ("0 0 0 named\n1 2 3", "artifact_verification_failed"),
    ],
)
def test_import_refuses_malformed_or_native_loss_without_publication(
    tmp_path: Path, runtime, record: str, failure: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime, "rgb")
    original = source.read_bytes()
    target.write_bytes(b"keep target")
    colors = tmp_path / "colors.gpl"
    colors.write_text("GIMP Palette\n" + record + "\n")
    code, result = run_palette(
        "palette",
        "import",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        palette_frame_number=3,
        palette_file={"format": "gpl", "path": str(colors)},
    )
    assert code != 0 and result["code"] == failure, result
    assert source.read_bytes() == original and target.read_bytes() == b"keep target"
