"""Palette organization through public operations and persisted native documents."""

from pathlib import Path

import pytest

from tests.palette.support import palette_fixture, run_palette

pytestmark = pytest.mark.e2e


def mutation(source: Path, target: Path, **values: object) -> dict:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
        **values,
    }


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_resize_grows_only_the_exact_change_with_explicit_colors(
    tmp_path: Path, runtime, mode: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime, mode)
    original = source.read_bytes()
    code, before = run_palette("palette", "list", sprite_file=str(source))
    assert code == 0, before
    entries = [
        {"index": 4, "color": {"red": 11, "green": 22, "blue": 33, "alpha": 44}},
        {"index": 5, "color": {"red": 55, "green": 66, "blue": 77, "alpha": 88}},
    ]
    code, result = run_palette(
        "palette",
        "resize",
        **mutation(source, target, palette_frame_number=3, size=6, entries=entries),
    )
    assert code == 0, result
    code, after = run_palette("palette", "list", sprite_file=str(target))
    assert code == 0, after
    expected = before["palette_changes"]
    expected[1]["entries"].extend(entries)
    assert after["palette_changes"] == expected
    assert result["palette_changes"] == expected
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original


def test_resize_shrinks_unused_entries_without_changing_pixels(
    tmp_path: Path, runtime
) -> None:
    source, grown, shrunk = (
        tmp_path / name
        for name in ("source.aseprite", "grown.aseprite", "shrunk.aseprite")
    )
    palette_fixture(source, runtime)
    code, original = run_palette("palette", "list", sprite_file=str(source))
    assert code == 0, original
    code, result = run_palette(
        "palette",
        "resize",
        **mutation(
            source,
            grown,
            palette_frame_number=3,
            size=5,
            entries=[
                {"index": 4, "color": {"red": 1, "green": 2, "blue": 3, "alpha": 255}}
            ],
        ),
    )
    assert code == 0, result
    code, result = run_palette(
        "palette",
        "resize",
        **mutation(grown, shrunk, palette_frame_number=3, size=4, entries=[]),
    )
    assert code == 0, result
    assert result["palette_changes"] == original["palette_changes"]


def test_resize_refuses_removing_transparent_index_before_publication(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    palette_fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    code, result = run_palette(
        "palette",
        "resize",
        **mutation(source, target, palette_frame_number=3, size=3, entries=[]),
    )
    assert code != 0 and result["code"] == "palette_transform_rejected", result
    assert result["details"]["reason"] == "transparent_index_removed"
    assert source.read_bytes() == original and target.read_bytes() == b"existing target"
