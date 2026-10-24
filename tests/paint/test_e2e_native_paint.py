"""Native Paint through the public CLI, with saved Image facts as evidence."""

from importlib.resources import files
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import Outcome, run, run_lua
from tests.paint.support import (
    FIXTURES,
    RED,
    create_sprite,
    native_fixture,
    read_pixels,
)
from tests.support import observe_cli, process_diagnostics

pytestmark = pytest.mark.e2e


def _paint(
    source: Path, destination: Path, primitive: str = "line", **options: object
) -> Outcome:
    """Run `spa paint <primitive>` on Layer 1, Frame 1 of source with a red 1 px brush.

    A line goes from (2, 2) to (5, 2); a shape has an outline in a 4 by 3 box at
    (2, 2). The options replace these fields.
    """
    geometry = {"from": {"x": 2, "y": 2}, "to": {"x": 5, "y": 2}}
    if primitive != "line":
        geometry = {
            "bounds": {"x": 2, "y": 2, "width": 4, "height": 3},
            "style": "outline",
        }
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(destination),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        "brush": {"kind": "circle", "size": 1},
        "color": RED,
        "ink": "simple",
        "opacity": 255,
        "clipping": "reject",
    }
    return run(f"paint {primitive}", request | geometry | options)


def test_line_persists_native_pixels_without_resizing_the_cel(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    create_sprite(source)
    original = source.read_bytes()
    outcome = _paint(source, target)
    result = outcome.envelope
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    assert (
        result["pixels_requested"]
        == result["pixels_written"]
        == result["pixels_changed"]
        == 4
    )
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original
    pixels = read_pixels(target)
    assert {
        (x, y)
        for y, row in enumerate(pixels)
        for x, color in enumerate(row)
        if color["alpha"]
    } == {
        (2, 2),
        (3, 2),
        (4, 2),
        (5, 2),
    }
    assert all(pixels[2][x] == RED for x in range(2, 6))


def test_filled_rectangle_uses_half_open_bounds(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "rectangle.aseprite"
    create_sprite(source)
    outcome = _paint(source, target, "rectangle", style="filled")
    result = outcome.envelope
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    assert result["pixels_changed"] == 12
    pixels = read_pixels(target)
    assert {
        (x, y)
        for y, row in enumerate(pixels)
        for x, color in enumerate(row)
        if color["alpha"]
    } == {(x, y) for y in (2, 3, 4) for x in (2, 3, 4, 5)}


def test_filled_ellipse_has_native_pixel_coverage(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "ellipse.aseprite"
    create_sprite(source)
    outcome = _paint(
        source,
        target,
        "ellipse",
        style="filled",
        bounds={"x": 2, "y": 2, "width": 3, "height": 3},
    )
    result = outcome.envelope
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    pixels = read_pixels(target)
    assert {
        (x, y)
        for y, row in enumerate(pixels)
        for x, color in enumerate(row)
        if color["alpha"]
    } == {
        (3, 2),
        (2, 3),
        (3, 3),
        (4, 3),
        (3, 4),
    }
    assert result["pixels_changed"] == 5


@pytest.mark.parametrize("in_place", [False, True])
def test_native_save_failure_after_drawing_never_publishes(
    tmp_path: Path, in_place: bool
) -> None:
    source = tmp_path / "source.aseprite"
    create_sprite(source)
    target = source if in_place else tmp_path / "target.aseprite"
    if not in_place:
        target.write_bytes(source.read_bytes())
    before_source, before_target = source.read_bytes(), target.read_bytes()
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": in_place,
        "overwrite": True,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "coordinate_space": "image-pixel",
        "from": {"x": 2, "y": 2},
        "to": {"x": 5, "y": 2},
        "brush": {"kind": "circle", "size": 1},
        "color": RED,
        "ink": "simple",
        "opacity": 255,
    }
    process, failure, observed = observe_cli(
        "blocked_stage",
        "paint line",
        request,
        tmp_path / "observations.json",
        seam="staged_path",
    )
    assert process.returncode == 1 and failure["code"] == "kernel_execution_failed", (
        failure
    )
    assert "could not reopen Native Paint" in failure["details"]["reason"], failure
    assert observed == {"commits": 0, "discarded": True}
    assert source.read_bytes() == before_source
    assert target.read_bytes() == before_target
    assert not list(tmp_path.rglob("*.staged.aseprite"))


@pytest.mark.parametrize(
    "primitive,style",
    [
        ("line", None),
        ("rectangle", "outline"),
        ("rectangle", "filled"),
        ("ellipse", "outline"),
        ("ellipse", "filled"),
    ],
)
@pytest.mark.parametrize(
    "ink", ["simple", "alpha-compositing", "copy-color", "lock-alpha"]
)
@pytest.mark.parametrize("opacity", [0, 128, 255])
def test_native_ink_opacity_parity_on_nonempty_image(
    runtime: RuntimeObservation,
    tmp_path: Path,
    primitive: str,
    style: str | None,
    ink: str,
    opacity: int,
) -> None:
    geometry = (
        {"from": {"x": 2, "y": 2}, "to": {"x": 5, "y": 2}}
        if primitive == "line"
        else {
            "bounds": {"x": 2, "y": 2, "width": 4, "height": 3},
            "style": style,
        }
    )
    source, expected = native_fixture(
        runtime,
        tmp_path,
        reference=True,
        tool=("filled_" if style == "filled" else "") + primitive,
        **geometry,
        ink=ink,
        opacity=opacity,
        brush={"kind": "circle", "size": 1},
    )
    target = tmp_path / "painted.aseprite"
    outcome = _paint(source, target, primitive, ink=ink, opacity=opacity, **geometry)
    result = outcome.envelope
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    assert read_pixels(target) == read_pixels(expected)
    assert result["requested_opacity"] == opacity
    assert result["effective_opacity"] == (
        255 if ink in {"simple", "copy-color"} else opacity
    )
    if opacity == 0 and ink in {"simple", "copy-color"}:
        assert result["pixels_changed"] > 0
    elif opacity == 0:
        assert result["pixels_changed"] == 0


@pytest.mark.parametrize("clipping", ["reject", "clip"])
def test_native_footprint_bounds_and_canvas_selection_on_offset_linked_cels(
    runtime: RuntimeObservation,
    tmp_path: Path,
    clipping: str,
) -> None:
    source, _ = native_fixture(runtime, tmp_path, linked=True, offset=True)
    original = source.read_bytes()
    target = tmp_path / "clipped.aseprite"
    outcome = _paint(
        source,
        target,
        clipping=clipping,
        brush={"kind": "circle", "size": 3},
        **{"from": {"x": 0, "y": 2}, "to": {"x": 0, "y": 2}},
        selection={
            "kind": "all",
            "rectangle": {"x": -2, "y": 4, "width": 1, "height": 3},
        },
    )
    result = outcome.envelope
    assert source.read_bytes() == original
    if clipping == "reject":
        assert outcome.returncode == 1, process_diagnostics(outcome.process)
        assert result["code"] == "kernel_execution_failed"
        assert (
            "Native Brush footprint is outside Image bounds"
            in result["details"]["reason"]
        )
        assert not target.exists()
        return
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    assert result["pixels_requested"] == 5
    assert result["pixels_skipped_by_bounds"] == 1
    assert result["pixels_skipped_by_selection"] == 1
    assert result["pixels_written"] == result["pixels_changed"] == 3
    assert [item["frame_number"] for item in result["affected_cels"]] == [1, 2]
    assert result["affected_cels"][0]["position"] == {"x": -2, "y": 3}
    assert result["linked_cels_preserved"] is True
    assert read_pixels(target) == read_pixels(target, frame=2)
    assert read_pixels(target, frame=3) == read_pixels(source, frame=3)
    pixels = read_pixels(target)
    assert {
        (x, y)
        for y, row in enumerate(pixels)
        for x, color in enumerate(row)
        if color == RED
    } == {
        (0, 1),
        (0, 2),
        (0, 3),
    }


@pytest.mark.parametrize(
    "primitive,style",
    [
        ("line", None),
        ("rectangle", "outline"),
        ("rectangle", "filled"),
        ("ellipse", "outline"),
        ("ellipse", "filled"),
    ],
)
@pytest.mark.parametrize(
    "mode,brush",
    [
        ("rgb", {"kind": "circle", "size": 3}),
        ("rgb", {"kind": "square", "size": 2, "angle": 45}),
        ("rgb", {"kind": "line", "size": 5, "angle": -45}),
        ("grayscale", {"kind": "line", "size": 3, "angle": 90}),
        ("indexed", {"kind": "square", "size": 3, "angle": 180}),
        ("indexed", {"kind": "line", "size": 3, "angle": -180}),
    ],
)
def test_brush_and_color_mode_parity(
    runtime: RuntimeObservation,
    tmp_path: Path,
    primitive: str,
    style: str | None,
    mode: str,
    brush: dict,
) -> None:
    geometry = (
        {"from": {"x": 2, "y": 2}, "to": {"x": 5, "y": 2}}
        if primitive == "line"
        else {
            "bounds": {"x": 2, "y": 2, "width": 4, "height": 3},
            "style": style,
        }
    )
    source, expected = native_fixture(
        runtime,
        tmp_path,
        reference=True,
        mode=mode,
        tool=("filled_" if style == "filled" else "") + primitive,
        **geometry,
        ink="alpha-compositing",
        opacity=128,
        brush=brush,
    )
    color = (
        RED
        if mode == "rgb"
        else {"kind": "grayscale", "gray": 200, "alpha": 255}
        if mode == "grayscale"
        else {"kind": "palette-index", "index": 2}
    )
    target = tmp_path / "painted.aseprite"
    outcome = _paint(
        source,
        target,
        primitive,
        ink="alpha-compositing",
        opacity=128,
        color=color,
        brush=brush,
        clipping="clip",
        **geometry,
    )
    result = outcome.envelope
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    assert read_pixels(target) == read_pixels(expected)
    assert result["brush"] == brush | {"angle": brush.get("angle", 0)}
    if mode == "indexed":
        assert result["effective_palettes"][0]["palette_size"] == 8


@pytest.mark.parametrize(
    "primitive,style",
    [
        ("rectangle", "outline"),
        ("rectangle", "filled"),
        ("ellipse", "outline"),
        ("ellipse", "filled"),
    ],
)
@pytest.mark.parametrize("width,height", [(1, 1), (1, 3), (3, 1)])
def test_degenerate_shape_retains_native_tool_behavior(
    runtime: RuntimeObservation,
    tmp_path: Path,
    primitive: str,
    style: str,
    width: int,
    height: int,
) -> None:
    bounds = {"x": 2, "y": 2, "width": width, "height": height}
    brush = {"kind": "circle", "size": 3}
    source, expected = native_fixture(
        runtime,
        tmp_path,
        reference=True,
        tool=("filled_" if style == "filled" else "") + primitive,
        bounds=bounds,
        ink="copy-color",
        opacity=0,
        brush=brush,
    )
    target = tmp_path / "painted.aseprite"
    outcome = _paint(
        source,
        target,
        primitive,
        bounds=bounds,
        style=style,
        brush=brush,
        ink="copy-color",
        opacity=0,
    )
    result = outcome.envelope
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    assert read_pixels(target) == read_pixels(expected)
    assert result["bounds"] == bounds and result["style"] == style


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("primitive", ["line", "rectangle", "ellipse"])
def test_background_targets_match_native_paint(
    runtime: RuntimeObservation, tmp_path: Path, mode: str, primitive: str
) -> None:
    geometry = (
        {"from": {"x": 2, "y": 2}, "to": {"x": 5, "y": 2}}
        if primitive == "line"
        else {
            "bounds": {"x": 2, "y": 2, "width": 4, "height": 3},
            "style": "filled",
        }
    )
    source, expected = native_fixture(
        runtime,
        tmp_path,
        reference=True,
        mode=mode,
        background=True,
        tool=("filled_" if primitive != "line" else "") + primitive,
        **geometry,
        ink="alpha-compositing",
        opacity=128,
        brush={"kind": "circle", "size": 1},
    )
    color = (
        RED
        if mode == "rgb"
        else {"kind": "grayscale", "gray": 200, "alpha": 255}
        if mode == "grayscale"
        else {"kind": "palette-index", "index": 2}
    )
    target = tmp_path / "painted.aseprite"
    outcome = _paint(
        source,
        target,
        primitive,
        ink="alpha-compositing",
        opacity=128,
        color=color,
        **geometry,
    )
    result = outcome.envelope
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    assert result["background_opaque"] is True
    assert read_pixels(target) == read_pixels(expected)


@pytest.mark.parametrize("primitive", ["line", "rectangle", "ellipse"])
def test_shading_gap_is_typed_and_never_publishes(
    runtime: RuntimeObservation, tmp_path: Path, primitive: str
) -> None:
    source, _ = native_fixture(runtime, tmp_path)
    original = source.read_bytes()
    target = tmp_path / "unchanged.aseprite"
    target.write_bytes(original)
    outcome = _paint(source, target, primitive, ink="shading", overwrite=True)
    result = outcome.envelope
    assert outcome.returncode == 2, process_diagnostics(outcome.process)
    assert result["code"] == "paint_capability_gap"
    assert result["details"]["gap"]["capability"] == "shading Ink"
    assert result["details"]["gap"]["aseprite_version"]
    assert source.read_bytes() == target.read_bytes() == original


@pytest.mark.parametrize("selection", [None, {"kind": "empty"}])
def test_hidden_pixels_and_explicit_empty_selection_are_preserved(
    runtime: RuntimeObservation, tmp_path: Path, selection: dict | None
) -> None:
    source, _ = native_fixture(runtime, tmp_path, hidden=True)
    target = tmp_path / "painted.aseprite"
    before = read_pixels(source)
    outcome = _paint(source, target, selection=selection)
    result = outcome.envelope
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    after = read_pixels(target)
    assert after[5][7] == {
        "kind": "rgba",
        "red": 17,
        "green": 31,
        "blue": 49,
        "alpha": 0,
    }
    if selection is not None:
        assert result["pixels_changed"] == result["pixels_written"] == 0
        assert result["pixels_skipped_by_selection"] == 4
        assert before == after
    else:
        assert result["pixels_changed"] == 4


@pytest.mark.parametrize(
    "tool",
    [
        "line",
        "rectangle",
        "filled_rectangle",
        "ellipse",
        "filled_ellipse",
        "pencil",
        "eraser",
        "paint_bucket",
    ],
)
def test_native_tool_state_is_restored_on_success_and_failure(
    runtime: RuntimeObservation, tmp_path: Path, tool: str
) -> None:
    from spa.authoring.raster.paint_native import NATIVE_PAINT_RESOURCES

    source, _ = native_fixture(runtime, tmp_path)
    blocked_parent = tmp_path / "blocked-stage-parent"
    blocked_parent.write_bytes(b"not a directory")
    kernel = files("spa.kernel")
    params = {
        "tool": tool,
        "source": str(source),
        "target": str(tmp_path / "painted.aseprite"),
        "failure": str(tmp_path / "failure.aseprite"),
        "unwritable": str(blocked_parent / "painted.aseprite"),
    }
    for resource in NATIVE_PAINT_RESOURCES:
        params[resource.parameter_name] = str(kernel.joinpath(resource.package_path))
    lua = run_lua(FIXTURES / "native_paint_isolation.lua", runtime, **params)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert (tmp_path / "painted.aseprite").is_file()
    assert not (tmp_path / "failure.aseprite").exists()


@pytest.mark.parametrize(
    "kind,code",
    [
        ("group", "cel_unsupported_target"),
        ("reference", "cel_unsupported_target"),
        ("tilemap", "cel_unsupported_target"),
        ("absent", "cel_not_found"),
    ],
)
@pytest.mark.parametrize("primitive", ["line", "rectangle", "ellipse"])
def test_unsupported_or_absent_targets_do_not_publish(
    runtime: RuntimeObservation, tmp_path: Path, kind: str, code: str, primitive: str
) -> None:
    source, _ = native_fixture(runtime, tmp_path, target_kind=kind)
    original = source.read_bytes()
    target = tmp_path / "unchanged.aseprite"
    target.write_bytes(original)
    outcome = _paint(
        source,
        target,
        primitive,
        overwrite=True,
        target={
            "layer": {"layer_path": [1]},
            "frame_number": 2 if kind == "absent" else 1,
        },
    )
    result = outcome.envelope
    assert outcome.returncode == 2, process_diagnostics(outcome.process)
    assert result["code"] == code
    assert source.read_bytes() == target.read_bytes() == original


def test_native_paint_supports_in_place(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source, _ = native_fixture(runtime, tmp_path)
    original = source.read_bytes()
    outcome = _paint(source, source, in_place=True, overwrite=True)
    result = outcome.envelope
    assert outcome.returncode == 0, process_diagnostics(outcome.process)
    assert source.read_bytes() != original
    assert result["pixels_changed"] == 4
