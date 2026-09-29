"""Native Paint through the public CLI, with saved Image facts as evidence."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e

RED = {"kind": "rgba", "red": 255, "green": 0, "blue": 0, "alpha": 255}


def _call(*command: str, **request: object):
    run = spa(
        *command,
        "--input-json",
        "-",
        stdin=json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"], **request}),
    )
    return run, json.loads(run.stdout) if run.stdout else {}


def _create(source: Path) -> None:
    run, result = _call(
        "sprite",
        "create",
        target_sprite_file=str(source),
        width=8,
        height=6,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=False,
    )
    assert run.returncode == 0, result


def _paint(source: Path, destination: Path, primitive: str = "line", **options: object):
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
    return _call("paint", primitive, **(request | geometry | options))


def _pixels(source: Path, *, frame: int = 1) -> list[list[dict]]:
    run, result = _call(
        "image",
        "get",
        sprite_file=str(source),
        source={
            "kind": "individual",
            "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
            "rectangle": {"x": 0, "y": 0, "width": 8, "height": 6},
        },
    )
    assert run.returncode == 0, result
    return [
        [segment["color"] for segment in row for _ in range(segment["length"])]
        for row in result["snapshot"]["rows"]
    ]


def test_line_persists_native_pixels_without_resizing_the_cel(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _create(source)
    original = source.read_bytes()
    run, result = _paint(source, target)
    assert run.returncode == 0, run.stdout + run.stderr
    assert (
        result["pixels_requested"]
        == result["pixels_written"]
        == result["pixels_changed"]
        == 4
    )
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original
    pixels = _pixels(target)
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
    _create(source)
    run, result = _paint(source, target, "rectangle", style="filled")
    assert run.returncode == 0, run.stdout + run.stderr
    assert result["pixels_changed"] == 12
    pixels = _pixels(target)
    assert {
        (x, y)
        for y, row in enumerate(pixels)
        for x, color in enumerate(row)
        if color["alpha"]
    } == {(x, y) for y in (2, 3, 4) for x in (2, 3, 4, 5)}


def test_filled_ellipse_has_native_pixel_coverage(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "ellipse.aseprite"
    _create(source)
    run, result = _paint(
        source,
        target,
        "ellipse",
        style="filled",
        bounds={"x": 2, "y": 2, "width": 3, "height": 3},
    )
    assert run.returncode == 0, run.stdout + run.stderr
    pixels = _pixels(target)
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


def _native_fixture(tmp_path: Path, *, reference: bool = False, **options: object):
    source = tmp_path / "source.aseprite"
    expected = tmp_path / "reference.aseprite"
    config = tmp_path / "native.json"
    config.write_text(json.dumps({"mode": "rgb", **options}))
    binary = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    # Use the same supported process layout as other real-runtime fixtures.
    selected = probe(RuntimeRequest(aseprite=str(binary)), PROBE_RESOURCES)
    (tmp_path / "runtime").mkdir()
    prepared = prepare_invocation(
        Path(selected.canonical_path),
        Path(selected.resource_path),
        tmp_path / "runtime",
    )
    args = [
        str(prepared.executable),
        "--batch",
        "--script-param",
        f"input={config}",
        "--script-param",
        f"source={source}",
    ]
    if reference:
        args += ["--script-param", f"reference={expected}"]
    args += [
        "--script",
        str(Path(__file__).parent / "fixtures" / "native_paint_reference.lua"),
    ]
    run = subprocess.run(
        args, capture_output=True, text=True, env=prepared.environment, check=False
    )
    assert run.returncode == 0, run.stdout + run.stderr
    return source, expected


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
    tmp_path: Path, primitive: str, style: str | None, ink: str, opacity: int
) -> None:
    geometry = (
        {"from": {"x": 2, "y": 2}, "to": {"x": 5, "y": 2}}
        if primitive == "line"
        else {
            "bounds": {"x": 2, "y": 2, "width": 4, "height": 3},
            "style": style,
        }
    )
    source, expected = _native_fixture(
        tmp_path,
        reference=True,
        tool=("filled_" if style == "filled" else "") + primitive,
        **geometry,
        ink=ink,
        opacity=opacity,
        brush={"kind": "circle", "size": 1},
    )
    target = tmp_path / "painted.aseprite"
    run, result = _paint(
        source, target, primitive, ink=ink, opacity=opacity, **geometry
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert _pixels(target) == _pixels(expected)
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
    tmp_path: Path,
    clipping: str,
) -> None:
    source, _ = _native_fixture(tmp_path, linked=True, offset=True)
    original = source.read_bytes()
    target = tmp_path / "clipped.aseprite"
    run, result = _paint(
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
    assert source.read_bytes() == original
    if clipping == "reject":
        assert run.returncode != 0
        assert "footprint is outside Image bounds" in result["details"]["reason"]
        assert not target.exists()
        return
    assert run.returncode == 0, run.stdout + run.stderr
    assert result["pixels_requested"] == 5
    assert result["pixels_skipped_by_bounds"] == 1
    assert result["pixels_skipped_by_selection"] == 1
    assert result["pixels_written"] == result["pixels_changed"] == 3
    assert [item["frame_number"] for item in result["affected_cels"]] == [1, 2]
    assert result["affected_cels"][0]["position"] == {"x": -2, "y": 3}
    assert result["linked_cels_preserved"] is True
    assert _pixels(target) == _pixels(target, frame=2)
    assert _pixels(target, frame=3) == _pixels(source, frame=3)
    pixels = _pixels(target)
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
    tmp_path: Path, primitive: str, style: str | None, mode: str, brush: dict
) -> None:
    geometry = (
        {"from": {"x": 2, "y": 2}, "to": {"x": 5, "y": 2}}
        if primitive == "line"
        else {
            "bounds": {"x": 2, "y": 2, "width": 4, "height": 3},
            "style": style,
        }
    )
    source, expected = _native_fixture(
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
    run, result = _paint(
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
    assert run.returncode == 0, run.stdout + run.stderr
    assert _pixels(target) == _pixels(expected)
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
    tmp_path: Path, primitive: str, style: str, width: int, height: int
) -> None:
    bounds = {"x": 2, "y": 2, "width": width, "height": height}
    brush = {"kind": "circle", "size": 3}
    source, expected = _native_fixture(
        tmp_path,
        reference=True,
        tool=("filled_" if style == "filled" else "") + primitive,
        bounds=bounds,
        ink="copy-color",
        opacity=0,
        brush=brush,
    )
    target = tmp_path / "painted.aseprite"
    run, result = _paint(
        source,
        target,
        primitive,
        bounds=bounds,
        style=style,
        brush=brush,
        ink="copy-color",
        opacity=0,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert _pixels(target) == _pixels(expected)
    assert result["bounds"] == bounds and result["style"] == style


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("primitive", ["line", "rectangle", "ellipse"])
def test_background_targets_match_native_paint(
    tmp_path: Path, mode: str, primitive: str
) -> None:
    geometry = (
        {"from": {"x": 2, "y": 2}, "to": {"x": 5, "y": 2}}
        if primitive == "line"
        else {
            "bounds": {"x": 2, "y": 2, "width": 4, "height": 3},
            "style": "filled",
        }
    )
    source, expected = _native_fixture(
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
    run, result = _paint(
        source,
        target,
        primitive,
        ink="alpha-compositing",
        opacity=128,
        color=color,
        **geometry,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert result["background_opaque"] is True
    assert _pixels(target) == _pixels(expected)


@pytest.mark.parametrize("primitive", ["line", "rectangle", "ellipse"])
def test_shading_gap_is_typed_and_never_publishes(
    tmp_path: Path, primitive: str
) -> None:
    source, _ = _native_fixture(tmp_path)
    original = source.read_bytes()
    target = tmp_path / "unchanged.aseprite"
    target.write_bytes(original)
    run, result = _paint(source, target, primitive, ink="shading", overwrite=True)
    assert run.returncode == 2, run.stdout + run.stderr
    assert result["code"] == "paint_capability_gap"
    assert result["details"]["gap"]["capability"] == "shading Ink"
    assert result["details"]["gap"]["aseprite_version"]
    assert source.read_bytes() == target.read_bytes() == original


@pytest.mark.parametrize("selection", [None, {"kind": "empty"}])
def test_hidden_pixels_and_explicit_empty_selection_are_preserved(
    tmp_path: Path, selection: dict | None
) -> None:
    source, _ = _native_fixture(tmp_path, hidden=True)
    target = tmp_path / "painted.aseprite"
    before = _pixels(source)
    run, result = _paint(source, target, selection=selection)
    assert run.returncode == 0, run.stdout + run.stderr
    after = _pixels(target)
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
    "tool", ["line", "rectangle", "filled_rectangle", "ellipse", "filled_ellipse"]
)
def test_native_tool_state_is_restored_on_success_and_failure(
    tmp_path: Path, tool: str
) -> None:
    from spa.paint_native import NATIVE_PAINT_RESOURCES

    source, _ = _native_fixture(tmp_path)
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    workspace = tmp_path / "isolation"
    workspace.mkdir()
    prepared = prepare_invocation(
        Path(observation.canonical_path), Path(observation.resource_path), workspace
    )
    kernel = Path(__file__).parents[2] / "src" / "spa" / "kernel"
    args = [str(prepared.executable), "--batch"]
    params = {
        "tool": tool,
        "source": str(source),
        "target": str(tmp_path / "painted.aseprite"),
        "failure": str(tmp_path / "failure.aseprite"),
    }
    for resource in NATIVE_PAINT_RESOURCES:
        params[resource.parameter_name] = str(kernel / resource.package_name)
    for name, value in params.items():
        args += ["--script-param", f"{name}={value}"]
    args += [
        "--script",
        str(Path(__file__).parent / "fixtures" / "native_paint_isolation.lua"),
    ]
    run = subprocess.run(
        args, text=True, capture_output=True, env=prepared.environment, check=False
    )
    assert run.returncode == 0, run.stdout + run.stderr
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
    tmp_path: Path, kind: str, code: str, primitive: str
) -> None:
    source, _ = _native_fixture(tmp_path, target_kind=kind)
    original = source.read_bytes()
    target = tmp_path / "unchanged.aseprite"
    target.write_bytes(original)
    run, result = _paint(
        source,
        target,
        primitive,
        overwrite=True,
        target={
            "layer": {"layer_path": [1]},
            "frame_number": 2 if kind == "absent" else 1,
        },
    )
    assert run.returncode == 2, run.stdout + run.stderr
    assert result["code"] == code
    assert source.read_bytes() == target.read_bytes() == original


def test_native_paint_supports_in_place_and_rejects_alias_to_target(
    tmp_path: Path,
) -> None:
    source, _ = _native_fixture(tmp_path)
    original = source.read_bytes()
    alias = tmp_path / "alias.aseprite"
    alias.symlink_to(source)
    for in_place in (False, True):
        run, result = _paint(alias, source, in_place=in_place, overwrite=True)
        assert run.returncode == 2 and result["code"] == "invalid_request"
        assert source.read_bytes() == original
    run, result = _paint(source, source, in_place=True, overwrite=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert source.read_bytes() != original
    assert result["pixels_changed"] == 4
