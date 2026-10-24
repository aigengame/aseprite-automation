"""Compare public Paint Composite with independent native drawImage observations."""

import json
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run_lua
from tests.paint.support import FIXTURES
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e

RGB_MODES = (
    "normal",
    "multiply",
    "screen",
    "overlay",
    "darken",
    "lighten",
    "color-dodge",
    "color-burn",
    "hard-light",
    "soft-light",
    "difference",
    "exclusion",
    "hue",
    "saturation",
    "color",
    "luminosity",
    "addition",
    "subtract",
    "divide",
)
GRAY_GAPS = ("hue", "saturation", "color", "luminosity", "addition")
GRAY_MODES = tuple(mode for mode in RGB_MODES if mode not in GRAY_GAPS)
OPACITIES = (0, 127, 255)
RGB_FRONT = {"kind": "rgba", "red": 210, "green": 50, "blue": 20, "alpha": 128}
GRAY_FRONT = {"kind": "grayscale", "gray": 200, "alpha": 128}
RGB_BACK = {"kind": "rgba", "red": 40, "green": 100, "blue": 180, "alpha": 128}


def _snapshot(mode: str, colors: list[dict]) -> dict:
    runs: list[dict] = []
    for color in colors:
        if runs and runs[-1]["color"] == color:
            runs[-1]["length"] += 1
        else:
            runs.append({"length": 1, "color": color})
    return {
        "coordinate_space": "image-pixel",
        "color_mode": mode,
        "rectangle": {"x": 0, "y": 0, "width": len(colors), "height": 1},
        "rows": [runs],
    }


def _composite(
    source: Path,
    target: Path,
    mode: str,
    colors: list[dict],
    *,
    blend: str = "normal",
    opacity: int = 127,
    selection: dict | None = None,
) -> dict:
    """Composite one row of colors at (0, 0) on Layer 1, Frame 1 into a new target.

    It returns the success envelope.
    """
    return expect_success(
        "paint composite",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "input": {"kind": "inline", "snapshot": _snapshot(mode, colors)},
            "position": {"x": 0, "y": 0},
            "opacity": opacity,
            "blend_mode": blend,
            "selection": selection,
        },
    )


def _pixel(path: Path, *, frame: int = 1, x: int = 0) -> dict:
    """Return the color of one Layer 1 pixel in row 0."""
    result = expect_success(
        "image get",
        {
            "sprite_file": str(path),
            "source": {
                "kind": "individual",
                "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
                "rectangle": {"x": x, "y": 0, "width": 1, "height": 1},
            },
        },
    )
    return result["snapshot"]["rows"][0][0]["color"]


@pytest.fixture(scope="module")
def native(
    runtime: RuntimeObservation, tmp_path_factory: pytest.TempPathFactory
) -> dict:
    """Write the `composite_modes.lua` Sprites and read its drawImage oracle.

    It checks three known oracle values before a test uses the oracle.
    """
    directory = tmp_path_factory.mktemp("composite-modes")
    paths = {
        name: directory / f"{name}.aseprite"
        for name in ("rgb", "grayscale", "linked", "background")
    }
    oracle_file = directory / "oracle.json"
    lua = run_lua(
        FIXTURES / "composite_modes.lua",
        runtime,
        **{f"{name}_file": path for name, path in paths.items()},
        oracle=oracle_file,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    assert all(path.is_file() for path in paths.values())
    oracle = json.loads(oracle_file.read_text())
    assert oracle["matrix"]["rgb"]["normal"]["127"] == {
        "kind": "rgba",
        "red": 108,
        "green": 80,
        "blue": 116,
        "alpha": 160,
    }
    assert oracle["matrix"]["grayscale"]["normal"]["127"] == {
        "kind": "grayscale",
        "gray": 128,
        "alpha": 160,
    }
    assert oracle["matrix"]["rgb"]["hue"]["127"] == {
        "kind": "rgba",
        "red": 100,
        "green": 82,
        "blue": 119,
        "alpha": 160,
    }
    return {"paths": paths, "oracle": oracle}


@pytest.mark.parametrize(
    "mode,blend,opacity",
    [("rgb", blend, opacity) for blend in RGB_MODES for opacity in OPACITIES]
    + [("grayscale", blend, opacity) for blend in GRAY_MODES for opacity in OPACITIES],
)
def test_supported_mode_matches_native_draw_image(
    native: dict, tmp_path: Path, mode: str, blend: str, opacity: int
) -> None:
    source = native["paths"][mode]
    target = tmp_path / "composited.aseprite"
    front = RGB_FRONT if mode == "rgb" else GRAY_FRONT
    original = source.read_bytes()

    result = _composite(source, target, mode, [front], blend=blend, opacity=opacity)

    assert result["persisted_reopen_verified"] is True
    assert result["blend_mode"] == blend
    assert result["opacity"] == opacity
    assert _pixel(target) == native["oracle"]["matrix"][mode][blend][str(opacity)]
    assert source.read_bytes() == original


def test_background_native_composite_stays_opaque(native: dict, tmp_path: Path) -> None:
    source = native["paths"]["background"]
    target = tmp_path / "background-out.aseprite"

    result = _composite(source, target, "rgb", [RGB_FRONT])

    assert result["background_opaque"] is True
    assert _pixel(target) == native["oracle"]["background"]
    assert _pixel(target)["alpha"] == 255


def test_linked_cels_share_one_native_composite(native: dict, tmp_path: Path) -> None:
    source = native["paths"]["linked"]
    target = tmp_path / "linked-out.aseprite"

    result = _composite(source, target, "rgb", [RGB_FRONT])

    assert result["native_sharing_preserved"] is True
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1, 2]
    assert [
        [link["frame_number"] for link in cel["linked_cels"]]
        for cel in result["affected_cels"]
    ] == [[2], [1]]
    assert _pixel(target, frame=1, x=0) == native["oracle"]["linked"]["0"]
    assert _pixel(target, frame=2, x=0) == native["oracle"]["linked"]["0"]
    assert _pixel(target, frame=1, x=1) == RGB_BACK


def test_selection_maps_canvas_to_offset_linked_cel(
    native: dict, tmp_path: Path
) -> None:
    source = native["paths"]["linked"]
    target = tmp_path / "selected-out.aseprite"
    selection = {
        "kind": "all",
        "rectangle": {"x": 2, "y": 0, "width": 1, "height": 1},
    }

    result = _composite(
        source, target, "rgb", [RGB_FRONT, RGB_FRONT], selection=selection
    )

    assert result["pixels_written"] == 1
    assert result["pixels_skipped_by_selection"] == 1
    assert result["applied_runs"] == [{"x": 1, "y": 0, "length": 1}]
    assert result["skipped_by_selection_runs"] == [{"x": 0, "y": 0, "length": 1}]
    for frame in (1, 2):
        assert _pixel(target, frame=frame, x=0) == RGB_BACK
        assert _pixel(target, frame=frame, x=1) == native["oracle"]["linked"]["1"]
