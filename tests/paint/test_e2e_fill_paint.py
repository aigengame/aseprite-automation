"""Compare public Fill with an independent native Aseprite Paint Bucket."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.paint.support import call_spa
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e

COLORS = {
    "rgb": {
        "paint": {"kind": "rgba", "red": 20, "green": 220, "blue": 20, "alpha": 255},
        "mark": {"kind": "rgba", "red": 240, "green": 20, "blue": 20, "alpha": 255},
    },
    "grayscale": {
        "paint": {"kind": "grayscale", "gray": 110, "alpha": 255},
        "mark": {"kind": "grayscale", "gray": 220, "alpha": 255},
    },
    "indexed": {
        "paint": {"kind": "palette-index", "index": 3},
        "mark": {"kind": "palette-index", "index": 1},
    },
}


def _point(x: int, y: int) -> dict[str, int]:
    return {"x": x, "y": y}


def _coordinates(region: dict) -> set[tuple[int, int]]:
    return {
        (x, row["y"])
        for row in region["rows"]
        for run in row["runs"]
        for x in range(run["x"], run["x"] + run["length"])
    }


def _oracle_coordinates(points: list[dict]) -> set[tuple[int, int]]:
    return {(point["x"], point["y"]) for point in points}


def _pixels(
    sprite: Path, *, frame: int = 1, size: tuple[int, int] = (8, 6)
) -> list[list[dict]]:
    code, result = call_spa(
        "image",
        "get",
        sprite_file=str(sprite),
        source={
            "kind": "individual",
            "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
            "rectangle": {"x": 0, "y": 0, "width": size[0], "height": size[1]},
        },
    )
    assert code == 0, result
    return [
        [run["color"] for run in row for _ in range(run["length"])]
        for row in result["snapshot"]["rows"]
    ]


def _fixture(tmp_path: Path, config: dict) -> tuple[Path, Path, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source.aseprite"
    reference = tmp_path / "native-reference.aseprite"
    oracle_file = tmp_path / "native-oracle.json"
    input_file = tmp_path / "fixture.json"
    input_file.write_text(json.dumps(config))
    selected = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    work = tmp_path / "reference-runtime"
    work.mkdir()
    prepared = prepare_invocation(
        Path(selected.canonical_path), Path(selected.resource_path), work
    )
    run = subprocess.run(
        [
            str(prepared.executable),
            "--batch",
            "--script-param",
            f"input={input_file}",
            "--script-param",
            f"source={source}",
            "--script-param",
            f"reference={reference}",
            "--script-param",
            f"oracle={oracle_file}",
            "--script",
            str(Path(__file__).parent / "fixtures" / "fill_paint_reference.lua"),
        ],
        text=True,
        capture_output=True,
        env=prepared.environment,
        check=False,
    )
    assert run.returncode == 0, process_diagnostics(run)
    return source, reference, json.loads(oracle_file.read_text())


def _case(
    tmp_path: Path,
    *,
    mode: str = "rgb",
    scenario: str = "diagonal",
    seed: tuple[int, int] = (1, 1),
    frame: int = 1,
    opacity: int = 255,
    ink: str = "simple",
    paint_color: str = "paint",
    tolerance: int = 0,
    contiguous: bool = True,
    connectivity: str | None = "eight-connected",
    refer_to: str = "active-layer",
    stop_at_grid: bool = False,
    background: bool = False,
    linked: bool = False,
    grid: dict | None = None,
    clipping: str = "reject",
    selection: dict | None = None,
) -> tuple[dict, list[list[dict]], dict, Path, Path]:
    config = {
        "mode": mode,
        "scenario": scenario,
        "seed": _point(*seed),
        "frame": frame,
        "opacity": opacity,
        "ink": ink,
        "paint_color": paint_color,
        "tolerance": tolerance,
        "contiguous": contiguous,
        "connectivity": connectivity,
        "refer_to": refer_to,
        "stop_at_grid": stop_at_grid,
        "background": background,
        "linked": linked,
        "selection": selection,
        "grid": grid,
    }
    source, reference, oracle = _fixture(tmp_path, config)
    original = source.read_bytes()
    target = tmp_path / "actual.aseprite"
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
        "coordinate_space": "image-pixel",
        "seed": _point(*seed),
        "opacity": opacity,
        "ink": ink,
        "color": COLORS[mode][paint_color],
        "tolerance": tolerance,
        "contiguous": contiguous,
        "connectivity": connectivity,
        "refer_to": refer_to,
        "stop_at_grid": stop_at_grid,
        "clipping": clipping,
        **({"selection": selection} if selection is not None else {}),
    }
    code, result = call_spa("paint", "fill", **request)
    assert code == 0, result
    assert source.read_bytes() == original
    assert result["persisted_reopen_verified"] is True
    assert result["seed"] == _point(*seed)
    assert result["source_scope"] == {
        "kind": refer_to,
        "frame_number": frame,
        "canvas_bounds": {"x": 0, "y": 0, "width": 8, "height": 6},
    }
    assert result["requested_opacity"] == opacity
    assert result["effective_opacity"] == (
        255 if ink in {"simple", "copy-color"} else opacity
    )
    for region, key in (
        ("requested_region", "requested"),
        ("applied_region", "applied"),
        ("clipped_region", "clipped"),
        ("selection_excluded_region", "excluded"),
    ):
        assert _coordinates(result[region]) == _oracle_coordinates(oracle[key])
        assert result[region]["pixel_count"] == len(oracle[key])
    assert result["pixels_requested"] == len(oracle["requested"])
    assert result["pixels_written"] == len(oracle["applied"])
    assert result["pixels_skipped_by_bounds"] == len(oracle["clipped"])
    assert result["pixels_skipped_by_selection"] == len(oracle["excluded"])
    dimensions = (3, 2) if scenario == "small" else (8, 6)
    actual, expected = (
        _pixels(target, frame=frame, size=dimensions),
        _pixels(reference, frame=frame, size=dimensions),
    )
    assert actual == expected
    before = _pixels(source, frame=frame, size=dimensions)
    changed = sum(
        a != b
        for actual_row, before_row in zip(actual, before, strict=True)
        for a, b in zip(actual_row, before_row, strict=True)
    )
    assert result["pixels_changed"] == changed
    assert (result["before_content_digest"] == result["after_content_digest"]) == (
        changed == 0
    )
    assert result["linked_cels_preserved"] is True
    assert result["geometry_unchanged"] is True
    return result, actual, oracle, source, target


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("refer_to", ["active-layer", "all-layers"])
@pytest.mark.parametrize("connectivity", ["four-connected", "eight-connected"])
def test_native_source_mode_and_connectivity(
    tmp_path: Path, mode: str, refer_to: str, connectivity: str
) -> None:
    scenario = "all" if refer_to == "all-layers" else "diagonal"
    seed = (2, 2) if scenario == "all" else (1, 1)
    result, _, oracle, _, _ = _case(
        tmp_path,
        mode=mode,
        scenario=scenario,
        seed=seed,
        refer_to=refer_to,
        connectivity=connectivity,
    )
    assert result["pixels_requested"] == len(oracle["requested"])
    if scenario == "diagonal":
        assert result["pixels_requested"] == (
            1 if connectivity == "four-connected" else 4
        )
    else:
        assert result["pixels_requested"] == 1


def test_active_and_visible_composite_use_different_matching_sources(
    tmp_path: Path,
) -> None:
    active, _, _, _, _ = _case(
        tmp_path / "active", scenario="all", seed=(2, 2), refer_to="active-layer"
    )
    composite, _, _, _, _ = _case(
        tmp_path / "composite", scenario="all", seed=(2, 2), refer_to="all-layers"
    )
    assert active["pixels_requested"] == 48
    assert composite["pixels_requested"] == 1


def test_all_layers_reads_only_the_addressed_frame(tmp_path: Path) -> None:
    result, _, _, _, _ = _case(
        tmp_path, scenario="all-frame2", frame=2, seed=(2, 2), refer_to="all-layers"
    )
    assert result["source_scope"]["frame_number"] == 2
    assert result["pixels_requested"] == 2


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_noncontiguous_ignores_connectivity(tmp_path: Path, mode: str) -> None:
    result, _, _, _, _ = _case(tmp_path, mode=mode, contiguous=False, connectivity=None)
    assert result["connectivity"] is None
    assert result["pixels_requested"] == 4


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("tolerance", [0, 255])
def test_tolerance_retains_native_color_mode(
    tmp_path: Path, mode: str, tolerance: int
) -> None:
    result, _, _, _, _ = _case(
        tmp_path,
        mode=mode,
        scenario="tolerance",
        tolerance=tolerance,
    )
    assert result["tolerance"] == tolerance
    assert result["pixels_requested"] == (4 if tolerance == 0 else 48)


@pytest.mark.parametrize(
    "ink", ["simple", "alpha-compositing", "copy-color", "lock-alpha"]
)
@pytest.mark.parametrize("opacity", [0, 128, 255])
def test_ink_and_opacity_match_native(tmp_path: Path, ink: str, opacity: int) -> None:
    result, _, _, _, _ = _case(tmp_path, ink=ink, opacity=opacity)
    assert result["pixels_requested"] == 4
    if ink == "alpha-compositing" and opacity == 0:
        assert result["pixels_changed"] == 0


@pytest.mark.parametrize("case", ["same-color", "alpha-zero"])
def test_requested_region_survives_noop(tmp_path: Path, case: str) -> None:
    args = (
        {"paint_color": "mark"}
        if case == "same-color"
        else {"ink": "alpha-compositing", "opacity": 0}
    )
    result, _, _, _, _ = _case(tmp_path, **args)
    assert result["pixels_requested"] == 4
    assert result["pixels_changed"] == 0


@pytest.mark.parametrize(
    "grid",
    [
        {"x": 1, "y": 1, "width": 3, "height": 3},
        {"x": -2, "y": -2, "width": 3, "height": 3},
    ],
)
def test_saved_grid_origin_controls_fill(tmp_path: Path, grid: dict) -> None:
    result, _, _, _, _ = _case(tmp_path, stop_at_grid=True, grid=grid)
    assert result["effective_grid_cell"] == {
        "x": grid["x"] + ((1 - grid["x"]) // grid["width"]) * grid["width"],
        "y": grid["y"] + ((1 - grid["y"]) // grid["height"]) * grid["height"],
        "width": grid["width"],
        "height": grid["height"],
    }
    assert 0 < result["pixels_requested"] < 4


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_background_remains_opaque(tmp_path: Path, mode: str) -> None:
    result, _, _, _, _ = _case(tmp_path, mode=mode, background=True)
    assert result["background_opaque"] is True
    assert result["pixels_requested"] == 4


def test_addressed_frame_and_linked_image(tmp_path: Path) -> None:
    result, _, _, _, target = _case(tmp_path, scenario="frame2", frame=2)
    assert result["source_scope"]["frame_number"] == 2
    assert result["pixels_requested"] == 4
    linked_result, _, _, linked_source, linked_target = _case(
        tmp_path / "linked", linked=True
    )
    assert [cel["frame_number"] for cel in linked_result["affected_cels"]] == [1, 2]
    assert _pixels(linked_target, frame=1) == _pixels(linked_target, frame=2)
    assert _pixels(linked_source, frame=1) == _pixels(linked_source, frame=2)
    assert _pixels(target, frame=1) != _pixels(target, frame=2)


def test_selection_filters_writes_after_native_matching(tmp_path: Path) -> None:
    selection = {
        "kind": "mask",
        "bounds": {"x": 0, "y": 0, "width": 5, "height": 1},
        "rows": [{"y": 0, "runs": [{"x": 0, "length": 1}, {"x": 4, "length": 1}]}],
    }
    result, _, _, _, _ = _case(
        tmp_path,
        scenario="uniform",
        seed=(0, 0),
        selection=selection,
        connectivity="four-connected",
    )
    assert result["pixels_requested"] == 48
    assert result["pixels_written"] == 2
    assert result["pixels_skipped_by_selection"] == 46


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_small_image_clips_to_original_extent(tmp_path: Path, mode: str) -> None:
    result, _, _, _, _ = _case(
        tmp_path,
        mode=mode,
        scenario="small",
        seed=(0, 0),
        clipping="clip",
    )
    assert result["pixels_requested"] > 6
    assert result["pixels_skipped_by_bounds"] > 0
    assert result["pixels_written"] <= 6


def test_rejects_unclipped_footprint_and_outside_canvas_seed(tmp_path: Path) -> None:
    for name, seed in (("bounds", (0, 0)), ("seed", (-3, 0))):
        case_dir = tmp_path / name
        case_dir.mkdir()
        config = {
            "mode": "rgb",
            "scenario": "small",
            "seed": _point(0, 0),
            "frame": 1,
            "opacity": 255,
            "ink": "simple",
            "paint_color": "paint",
            "tolerance": 0,
            "contiguous": True,
            "connectivity": "eight-connected",
            "refer_to": "active-layer",
            "stop_at_grid": False,
        }
        source, _, _ = _fixture(case_dir, config)
        original = source.read_bytes()
        destination = case_dir / "rejected.aseprite"
        code, _ = call_spa(
            "paint",
            "fill",
            source_sprite_file=str(source),
            target_sprite_file=str(destination),
            in_place=False,
            overwrite=False,
            target={"layer": {"layer_path": [1]}, "frame_number": 1},
            coordinate_space="image-pixel",
            seed=_point(*seed),
            opacity=255,
            ink="simple",
            color=COLORS["rgb"]["paint"],
            tolerance=0,
            contiguous=True,
            connectivity="eight-connected",
            refer_to="active-layer",
            stop_at_grid=False,
            clipping="reject",
        )
        assert code != 0
        assert not destination.exists()
        assert source.read_bytes() == original
