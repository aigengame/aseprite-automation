"""Compare public freehand Paint with an independent native Aseprite stroke."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from tests.paint.support import call_spa

pytestmark = pytest.mark.e2e

COLORS = {
    "rgb": (
        {"kind": "rgba", "red": 255, "green": 0, "blue": 0, "alpha": 255},
        {"kind": "rgba", "red": 0, "green": 0, "blue": 255, "alpha": 255},
    ),
    "grayscale": (
        {"kind": "grayscale", "gray": 220, "alpha": 255},
        {"kind": "grayscale", "gray": 30, "alpha": 255},
    ),
    "indexed": (
        {"kind": "palette-index", "index": 1},
        {"kind": "palette-index", "index": 2},
    ),
}
PATHS = {
    "single": [(2, 2)],
    "straight": [(1, 1), (5, 1)],
    "reverse": [(5, 1), (1, 1)],
    "repeat": [(1, 1), (5, 1), (1, 1)],
    "corner": [(1, 2), (4, 2), (4, 4)],
    "corner_reversed": [(4, 4), (4, 2), (1, 2)],
    "edge": [(-1, 2), (2, 2)],
}


def _points(name: str) -> list[dict[str, int]]:
    return [{"x": x, "y": y} for x, y in PATHS[name]]


def _pixels(sprite: Path, frame: int = 1) -> list[list[dict]]:
    code, result = call_spa(
        "image",
        "get",
        sprite_file=str(sprite),
        source={
            "kind": "individual",
            "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
            "rectangle": {"x": 0, "y": 0, "width": 8, "height": 6},
        },
    )
    assert code == 0, result
    return [
        [run["color"] for run in row for _ in range(run["length"])]
        for row in result["snapshot"]["rows"]
    ]


def _fixture(tmp_path: Path, config: dict) -> tuple[Path, Path]:
    source, reference = tmp_path / "source.aseprite", tmp_path / "reference.aseprite"
    config_path = tmp_path / "reference.json"
    config_path.write_text(json.dumps(config))
    binary = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    selected = probe(RuntimeRequest(aseprite=str(binary)), PROBE_RESOURCES)
    work = tmp_path / "native-runtime"
    work.mkdir()
    prepared = prepare_invocation(
        Path(selected.canonical_path), Path(selected.resource_path), work
    )
    run = subprocess.run(
        [
            str(prepared.executable),
            "--batch",
            "--script-param",
            f"input={config_path}",
            "--script-param",
            f"source={source}",
            "--script-param",
            f"reference={reference}",
            "--script",
            str(Path(__file__).parent / "fixtures" / "freehand_paint_reference.lua"),
        ],
        text=True,
        capture_output=True,
        env=prepared.environment,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    return source, reference


def _case(
    tmp_path: Path,
    *,
    tool: str,
    mode: str = "rgb",
    algorithm: str = "regular",
    path: str = "straight",
    opacity: int = 255,
    ink: str = "simple",
    background: bool = False,
    replace: bool = False,
    linked: bool = False,
    selection: dict | None = None,
    clipping: str = "reject",
    brush: dict | None = None,
) -> tuple[dict, list[list[dict]], Path, Path]:
    fg, bg = COLORS[mode]
    points = _points(path)
    brush = brush or {"kind": "circle", "size": 1}
    behavior = (
        {
            "kind": "replace-foreground-with-background",
            "foreground_color": fg,
            "background_color": bg,
        }
        if replace
        else {"kind": "erase", **({"background_color": bg} if background else {})}
    )
    config = {
        "mode": mode,
        "tool": tool,
        "algorithm": algorithm,
        "points": points,
        "opacity": opacity,
        "ink": ink,
        "brush": brush,
        "color": fg,
        "behavior": behavior,
        "background": background,
        "linked": linked,
        "selection": selection,
        "fallback_foreground": fg,
        "fallback_background": bg,
    }
    source, reference = _fixture(tmp_path, config)
    original = source.read_bytes()
    target = tmp_path / "actual.aseprite"
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        "points": points,
        "freehand_algorithm": algorithm,
        "brush": brush,
        "opacity": opacity,
        "clipping": clipping,
        **({"selection": selection} if selection else {}),
        **({"color": fg, "ink": ink} if tool == "pencil" else {"behavior": behavior}),
    }
    code, result = call_spa("paint", tool, **request)
    assert code == 0, result
    assert source.read_bytes() == original
    assert result["persisted_reopen_verified"] is True
    assert result["points"] == points
    assert result["freehand_algorithm"] == algorithm
    assert result["requested_opacity"] == opacity
    effective = 255 if tool == "pencil" and ink in {"simple", "copy-color"} else opacity
    assert result["effective_opacity"] == effective
    assert result["pixels_requested"] == result["requested_region"]["pixel_count"]
    assert result["pixels_written"] == result["applied_region"]["pixel_count"]
    assert result["pixels_changed"] <= result["pixels_written"]
    actual, expected = _pixels(target), _pixels(reference)
    assert actual == expected
    original_pixels = _pixels(source)
    changed = sum(
        actual[y][x] != original_pixels[y][x] for y in range(6) for x in range(8)
    )
    assert result["pixels_changed"] == changed
    assert (result["before_content_digest"] == result["after_content_digest"]) == (
        changed == 0
    )
    if mode == "indexed":
        assert result["effective_palettes"][0]["palette_size"] == 8
    return result, actual, source, target


@pytest.mark.parametrize("algorithm", ["regular", "pixel-perfect", "dots"])
@pytest.mark.parametrize(
    "path", ["single", "straight", "reverse", "repeat", "corner", "corner_reversed"]
)
def test_pencil_path_and_algorithm_match_native(
    tmp_path: Path, algorithm: str, path: str
) -> None:
    result, actual, _, _ = _case(
        tmp_path,
        tool="pencil",
        algorithm=algorithm,
        path=path,
        ink="alpha-compositing",
        opacity=128,
    )
    if algorithm == "dots" and path == "straight":
        assert actual[1][1] == actual[1][5] != actual[1][3]
        assert result["pixels_requested"] == 2
    if algorithm == "pixel-perfect" and path == "corner":
        assert result["pixels_requested"] < 6


@pytest.mark.parametrize(
    "ink", ["simple", "alpha-compositing", "copy-color", "lock-alpha"]
)
@pytest.mark.parametrize("opacity", [0, 128, 255])
def test_pencil_ink_opacity_match_native(
    tmp_path: Path, ink: str, opacity: int
) -> None:
    _case(tmp_path, tool="pencil", ink=ink, opacity=opacity)


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("background", [False, True])
@pytest.mark.parametrize("replace", [False, True])
@pytest.mark.parametrize("opacity", [0, 128, 255])
def test_eraser_behavior_mode_layer_and_opacity_match_native(
    tmp_path: Path, mode: str, background: bool, replace: bool, opacity: int
) -> None:
    result, _, _, _ = _case(
        tmp_path,
        tool="eraser",
        mode=mode,
        background=background,
        replace=replace,
        opacity=opacity,
        path="single",
    )
    assert result["native_behavior"] == (
        "foreground-replacement"
        if replace
        else "background-color"
        if background
        else "transparent-index"
        if mode == "indexed"
        else "alpha-erasure"
    )
    assert result["transparent_index"] == (
        7 if mode == "indexed" and not background and not replace else None
    )
    assert result["behavior"]["kind"] == (
        "replace-foreground-with-background" if replace else "erase"
    )


@pytest.mark.parametrize("algorithm", ["regular", "pixel-perfect", "dots"])
@pytest.mark.parametrize("replace", [False, True])
def test_eraser_algorithm_and_replacement_match_native(
    tmp_path: Path, algorithm: str, replace: bool
) -> None:
    _case(
        tmp_path,
        tool="eraser",
        algorithm=algorithm,
        replace=replace,
        path="corner",
        opacity=128,
    )


@pytest.mark.parametrize("tool", ["pencil", "eraser"])
def test_linked_cels_preserve_native_pixels(tmp_path: Path, tool: str) -> None:
    result, _, _, target = _case(
        tmp_path,
        tool=tool,
        linked=True,
        path="corner",
        opacity=128,
    )
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1, 2]
    assert result["linked_cels_preserved"] is True
    assert _pixels(target, 1) == _pixels(target, 2)


@pytest.mark.parametrize("tool", ["pencil", "eraser"])
def test_clipped_and_selected_gesture_matches_native(tmp_path: Path, tool: str) -> None:
    selection = {"kind": "all", "rectangle": {"x": 0, "y": 2, "width": 2, "height": 1}}
    result, _, _, _ = _case(
        tmp_path,
        tool=tool,
        path="edge",
        clipping="clip",
        selection=selection,
        brush={"kind": "circle", "size": 1},
    )
    assert result["pixels_skipped_by_bounds"] > 0
    assert result["pixels_skipped_by_selection"] > 0


@pytest.mark.parametrize("tool", ["pencil", "eraser"])
def test_rejects_off_image_footprint_without_publishing(
    tmp_path: Path, tool: str
) -> None:
    source, _ = _fixture(
        tmp_path,
        {
            "mode": "rgb",
            "tool": tool,
            "algorithm": "regular",
            "points": _points("edge"),
            "opacity": 255,
            "ink": "simple",
            "brush": {"kind": "circle", "size": 1},
            "color": COLORS["rgb"][0],
            "behavior": {"kind": "erase"},
            "background": False,
            "linked": False,
            "selection": None,
            "fallback_foreground": COLORS["rgb"][0],
            "fallback_background": COLORS["rgb"][1],
        },
    )
    target = tmp_path / "refused.aseprite"
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        "points": _points("edge"),
        "freehand_algorithm": "regular",
        "brush": {"kind": "circle", "size": 1},
        "opacity": 255,
        "clipping": "reject",
        **(
            {"color": COLORS["rgb"][0], "ink": "simple"}
            if tool == "pencil"
            else {"behavior": {"kind": "erase"}}
        ),
    }
    original = source.read_bytes()
    code, result = call_spa("paint", tool, **request)
    assert code != 0, result
    assert not target.exists()
    assert source.read_bytes() == original
