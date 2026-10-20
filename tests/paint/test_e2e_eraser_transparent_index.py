"""An Indexed erase uses the Sprite mask, even without a matching Palette Entry."""

from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run, run_lua
from tests.paint.support import FIXTURES
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e

NATIVE = FIXTURES / "eraser_transparent_index.lua"


def _erase(source: Path, target: Path, *, frame: int = 1, **changes: object) -> dict:
    """Return a `paint eraser` request for one erase at (1, 0) on Layer 1.

    The request writes a new target at full opacity. The changes replace these
    fields.
    """
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
        "coordinate_space": "image-pixel",
        "points": [{"x": 1, "y": 0}],
        "freehand_algorithm": "regular",
        "brush": {"kind": "circle", "size": 1},
        "opacity": 255,
        "behavior": {"kind": "erase"},
    }
    return request | changes


@pytest.mark.parametrize("linked", [False, True])
def test_erase_uses_transparent_index_outside_effective_palette(
    runtime: RuntimeObservation, tmp_path: Path, linked: bool
) -> None:
    source = tmp_path / "source.aseprite"
    reference = tmp_path / "native.aseprite"
    target = tmp_path / "erased.aseprite"
    lua = run_lua(NATIVE, runtime, source=source, reference=reference, linked=linked)
    assert lua.returncode == 0, process_diagnostics(lua)
    original = source.read_bytes()

    result = expect_success(
        "paint eraser", _erase(source, target, frame=2 if linked else 1)
    )

    assert result["native_behavior"] == "transparent-index"
    assert result["transparent_index"] == 7
    assert result["pixels_changed"] == 1
    assert result["effective_palettes"] == [
        {
            "frame_number": frame,
            "palette_frame_number": 1,
            "palette_size": 2,
            "indexes": [],
        }
        for frame in ([1, 2] if linked else [1])
    ]
    assert [cel["frame_number"] for cel in result["affected_cels"]] == (
        [1, 2] if linked else [1]
    )
    assert result["linked_cels_preserved"] and result["geometry_unchanged"]
    assert result["persisted_reopen_verified"]
    assert source.read_bytes() == original
    lua = run_lua(NATIVE, runtime, reference=reference, target=target)
    assert lua.returncode == 0, process_diagnostics(lua)


def test_eraser_still_rejects_missing_palette_backed_color(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    lua = run_lua(
        NATIVE, runtime, source=source, reference=tmp_path / "native.aseprite"
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    original = source.read_bytes()
    target.write_bytes(original)

    outcome = run(
        "paint eraser",
        _erase(
            source,
            target,
            overwrite=True,
            behavior={
                "kind": "replace-foreground-with-background",
                "foreground_color": {"kind": "palette-index", "index": 1},
                "background_color": {"kind": "palette-index", "index": 2},
            },
        ),
    )
    result = outcome.envelope

    assert outcome.returncode == 1 and result["code"] == "kernel_execution_failed", (
        result
    )
    assert "Palette Index does not exist" in result["details"]["reason"]
    assert source.read_bytes() == target.read_bytes() == original
    assert not list(tmp_path.rglob("*.staged.aseprite"))
