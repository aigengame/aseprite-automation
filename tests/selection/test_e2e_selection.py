"""Explicit Selection values through the public CLI and real Aseprite."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from tests.native_invocation import expect_success, run

pytestmark = pytest.mark.e2e


@pytest.fixture
def windows_selection_directory():
    """Keep tilde inputs under home without changing the native launch environment."""
    assert os.name == "nt"
    with tempfile.TemporaryDirectory(
        prefix="spa-selection-", dir=Path.home()
    ) as directory:
        yield Path(directory)


def canvas_request(**fields: object) -> dict:
    """Return a Selection request with fields in canvas-pixel coordinates."""
    return {"coordinate_space": "canvas-pixel", **fields}


def test_create_rectangle_retains_absolute_canvas_coordinates() -> None:
    rectangle = {"x": -3, "y": 7, "width": 4, "height": 2}
    result = expect_success(
        "selection create",
        canvas_request(shape={"kind": "rectangle", "rectangle": rectangle}),
    )
    assert result["selection"] == {"kind": "all", "rectangle": rectangle}
    assert result["bounds"] == rectangle
    assert result["pixel_count"] == 8
    assert result["coordinate_space"] == "canvas-pixel"


@pytest.mark.parametrize(("width", "height"), [(1, 1), (1, 5), (5, 1)])
def test_degenerate_ellipse_uses_inclusive_native_endpoints(width, height) -> None:
    bounds = {"x": 11, "y": -8, "width": width, "height": height}
    result = expect_success(
        "selection create", canvas_request(shape={"kind": "ellipse", "bounds": bounds})
    )
    assert result["selection"] == {"kind": "all", "rectangle": bounds}
    assert result["pixel_count"] == width * height


def coverage(value: dict) -> set[tuple[int, int]]:
    if value["kind"] == "empty":
        return set()
    if value["kind"] == "all":
        r = value["rectangle"]
        return {
            (x, y)
            for y in range(r["y"], r["y"] + r["height"])
            for x in range(r["x"], r["x"] + r["width"])
        }
    return {
        (x, row["y"])
        for row in value["rows"]
        for run in row["runs"]
        for x in range(run["x"], run["x"] + run["length"])
    }


@pytest.mark.parametrize(
    ("mode", "xs"),
    [
        ("union", [-2, -1, 0, 1]),
        ("intersect", [-1, 0]),
        ("subtract", [-2]),
        ("xor", [-2, 1]),
    ],
)
def test_combine_uses_native_set_operations(mode, xs) -> None:
    left = {"kind": "all", "rectangle": {"x": -2, "y": 5, "width": 3, "height": 1}}
    right = {"kind": "all", "rectangle": {"x": -1, "y": 5, "width": 3, "height": 1}}
    result = expect_success(
        "selection combine", canvas_request(mode=mode, left=left, right=right)
    )
    assert coverage(result["selection"]) == {(x, 5) for x in xs}
    assert result["pixel_count"] == len(xs)


ASYMMETRIC = {
    "kind": "mask",
    "bounds": {"x": 10, "y": 20, "width": 4, "height": 2},
    "rows": [
        {"y": 20, "runs": [{"x": 10, "length": 1}]},
        {"y": 21, "runs": [{"x": 10, "length": 4}]},
    ],
}


def test_create_mask_and_finite_inversion_keep_nonzero_origin() -> None:
    created = expect_success(
        "selection create", canvas_request(shape={"kind": "mask", "input": ASYMMETRIC})
    )
    assert created["selection"] == ASYMMETRIC
    inverted = expect_success(
        "selection invert",
        canvas_request(selection=created["selection"], canvas=ASYMMETRIC["bounds"]),
    )
    assert coverage(inverted["selection"]) == {(11, 20), (12, 20), (13, 20)}


@pytest.mark.parametrize(
    "value", [{"kind": "empty"}, {"kind": "all", "rectangle": ASYMMETRIC["bounds"]}]
)
def test_invert_empty_and_full(value) -> None:
    result = expect_success(
        "selection invert", canvas_request(selection=value, canvas=ASYMMETRIC["bounds"])
    )
    assert result["pixel_count"] == (8 if value["kind"] == "empty" else 0)
    assert result["selection"]["kind"] == (
        "all" if value["kind"] == "empty" else "empty"
    )


def pixels(rows: list[str], x=10, y=20) -> set[tuple[int, int]]:
    return {
        (x + col, y + row)
        for row, line in enumerate(rows)
        for col, c in enumerate(line)
        if c == "#"
    }


@pytest.mark.parametrize(
    ("shape", "radius", "rows"),
    [
        ("circle", 1, [".#.", "###", ".#."]),
        ("square", 1, ["###", "###", "###"]),
        ("circle", 2, [".###.", "#####", "#####", "#####", ".###."]),
        ("square", 2, ["#####"] * 5),
    ],
)
def test_grow_uses_native_brush_footprint(shape, radius, rows) -> None:
    value = {"kind": "all", "rectangle": {"x": 12, "y": 22, "width": 1, "height": 1}}
    area = {"x": 8, "y": 18, "width": 9, "height": 9}
    result = expect_success(
        "selection grow",
        canvas_request(selection=value, canvas=area, shape=shape, radius=radius),
    )
    assert coverage(result["selection"]) == pixels(rows, 12 - radius, 22 - radius)
    assert (result["shape"], result["radius"], result["canvas"]) == (
        shape,
        radius,
        area,
    )


@pytest.mark.parametrize(
    ("transform", "rows"),
    [
        ({"kind": "flip", "axis": "horizontal"}, ["...#", "####"]),
        ({"kind": "flip", "axis": "vertical"}, ["####", "#..."]),
        ({"kind": "rotate", "angle": 90}, ["##", "#.", "#.", "#."]),
        ({"kind": "rotate", "angle": -90}, [".#", ".#", ".#", "##"]),
        ({"kind": "rotate", "angle": 180}, ["####", "...#"]),
        ({"kind": "scale", "width": 2, "height": 1}, ["#"]),
    ],
)
def test_transform_keeps_tight_bounds_placement_separate_from_actual_coverage(
    transform, rows
) -> None:
    area = {"x": 5, "y": 15, "width": 20, "height": 20}
    result = expect_success(
        "selection transform",
        canvas_request(selection=ASYMMETRIC, canvas=area, transform=transform),
    )
    assert coverage(result["selection"]) == pixels(rows)
    assert result["source_bounds"] == ASYMMETRIC["bounds"]
    assert (result["target_placement"]["x"], result["target_placement"]["y"]) == (
        10,
        20,
    )
    if transform["kind"] == "scale":
        assert result["target_placement"]["width"] == 2
        assert result["bounds"]["width"] == 1


def mask_value(rows: list[str], x=10, y=20) -> dict:
    """Build canonical wire fixtures from independently specified binary grids."""
    encoded = []
    for dy, line in enumerate(rows):
        runs = []
        start = None
        for dx, char in enumerate(line + "."):
            if char == "#" and start is None:
                start = dx
            if char != "#" and start is not None:
                runs.append({"x": x + start, "length": dx - start})
                start = None
        if runs:
            encoded.append({"y": y + dy, "runs": runs})
    return {
        "kind": "mask",
        "bounds": {"x": x, "y": y, "width": len(rows[0]), "height": len(rows)},
        "rows": encoded,
    }


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (["..#.", "#..#"], {(11, 20)}),
        ([".#.#", "#..."], set()),
    ],
)
def test_downscale_retains_survivor_offset_or_becomes_empty(rows, expected) -> None:
    result = expect_success(
        "selection transform",
        canvas_request(
            selection=mask_value(rows),
            canvas=ASYMMETRIC["bounds"],
            transform={"kind": "scale", "width": 2, "height": 1},
        ),
    )
    assert coverage(result["selection"]) == expected
    assert result["target_placement"] == {"x": 10, "y": 20, "width": 2, "height": 1}
    assert result["bounds"] == (
        {"x": 11, "y": 20, "width": 1, "height": 1} if expected else None
    )


@pytest.mark.parametrize(
    ("width", "height", "rows"),
    [
        (4, 2, ["#...", "####"]),
        (8, 4, ["##......", "##......", "########", "########"]),
    ],
)
def test_nearest_scale_same_size_and_upscale(width, height, rows) -> None:
    result = expect_success(
        "selection transform",
        canvas_request(
            selection=ASYMMETRIC,
            canvas={"x": 10, "y": 20, "width": 8, "height": 4},
            transform={"kind": "scale", "width": width, "height": height},
        ),
    )
    assert coverage(result["selection"]) == pixels(rows)


@pytest.mark.parametrize(("x", "y"), [(3, 2), (-3, -2)])
def test_translate_applies_integer_displacement(x, y) -> None:
    result = expect_success(
        "selection transform",
        canvas_request(
            selection=ASYMMETRIC,
            canvas={"x": 0, "y": 0, "width": 30, "height": 30},
            transform={"kind": "translate", "offset": {"x": x, "y": y}},
        ),
    )
    assert coverage(result["selection"]) == pixels(["#...", "####"], 10 + x, 20 + y)


@pytest.mark.parametrize("shape", ["circle", "square"])
@pytest.mark.parametrize("radius", [1, 2])
def test_shrink_erodes_complete_coverage(shape, radius) -> None:
    area = {"x": 10, "y": 20, "width": 7, "height": 7}
    result = expect_success(
        "selection shrink",
        canvas_request(
            selection={"kind": "all", "rectangle": area},
            canvas=area,
            shape=shape,
            radius=radius,
        ),
    )
    assert coverage(result["selection"]) == pixels(
        ["#" * (7 - 2 * radius)] * (7 - 2 * radius), 10 + radius, 20 + radius
    )


@pytest.mark.parametrize(
    ("shape", "rows"),
    [
        ("circle", ["#####", "##.##", "#...#", "##.##", "#####"]),
        ("square", ["#####", "#...#", "#...#", "#...#", "#####"]),
    ],
)
def test_shrink_with_hole_compares_complete_native_coverage(shape, rows) -> None:
    value = mask_value(
        ["#######", "#######", "#######", "###.###", "#######", "#######", "#######"]
    )
    result = expect_success(
        "selection shrink",
        canvas_request(selection=value, canvas=value["bounds"], shape=shape, radius=1),
    )
    assert coverage(result["selection"]) == pixels(rows, 11, 21)


@pytest.mark.parametrize("operation", ["grow", "shrink", "transform"])
def test_empty_remains_empty_with_valid_parameters(operation) -> None:
    params = (
        {"transform": {"kind": "scale", "width": 2, "height": 3}}
        if operation == "transform"
        else {"shape": "square", "radius": 2}
    )
    result = expect_success(
        f"selection {operation}",
        canvas_request(
            selection={"kind": "empty"}, canvas=ASYMMETRIC["bounds"], **params
        ),
    )
    assert result["selection"] == {"kind": "empty"}
    assert result["bounds"] is None
    if operation == "transform":
        assert result["source_bounds"] is None and result["target_placement"] is None


def test_grow_clips_but_transform_refuses_outside_selected_coverage() -> None:
    area = {"x": 10, "y": 20, "width": 3, "height": 3}
    value = {"kind": "all", "rectangle": {**area, "width": 1, "height": 1}}
    grown = expect_success(
        "selection grow",
        canvas_request(selection=value, canvas=area, shape="circle", radius=1),
    )
    assert coverage(grown["selection"]) == {(10, 20), (11, 20), (10, 21)}
    outcome = run(
        "selection transform",
        canvas_request(
            selection=value,
            canvas=area,
            transform={"kind": "translate", "offset": {"x": -1, "y": 0}},
        ),
    )
    refused = outcome.envelope
    assert outcome.returncode != 0 and refused["code"] == "selection_out_of_bounds", (
        refused
    )
    eroded = expect_success(
        "selection shrink",
        canvas_request(selection=value, canvas=area, shape="circle", radius=1),
    )
    assert eroded["selection"] == {"kind": "empty"}, eroded


@pytest.mark.parametrize("operation", ["invert", "grow", "shrink", "transform"])
def test_input_outside_canvas_is_rejected_before_processing(operation) -> None:
    params = (
        {"transform": {"kind": "scale", "width": 1, "height": 1}}
        if operation == "transform"
        else (
            {"shape": "circle", "radius": 1} if operation in {"grow", "shrink"} else {}
        )
    )
    outcome = run(
        f"selection {operation}",
        canvas_request(
            selection=ASYMMETRIC,
            canvas={"x": 11, "y": 20, "width": 3, "height": 2},
            **params,
        ),
    )
    result = outcome.envelope
    assert outcome.returncode != 0 and result["code"] == "selection_out_of_bounds", (
        result
    )


def test_validate_returns_findings_without_repair() -> None:
    result = expect_success(
        "selection validate",
        canvas_request(
            selection=ASYMMETRIC, canvas={"x": 11, "y": 20, "width": 3, "height": 2}
        ),
    )
    assert result["valid"] is False
    assert "selection_out_of_bounds" in {item["kind"] for item in result["findings"]}


@pytest.mark.parametrize("spelling", ["absolute", "tilde"])
def test_export_roundtrip_and_preview_use_explicit_canvas(
    tmp_path, request, spelling
) -> None:
    import hashlib

    from spa.adapters.png import verify_png

    if os.name == "nt" and spelling == "tilde":
        tmp_path = request.getfixturevalue("windows_selection_directory")
    destination = tmp_path / "mask.json"
    exported = expect_success(
        "selection export",
        canvas_request(
            selection=ASYMMETRIC,
            destination={"path": str(destination), "if_exists": "fail"},
        ),
    )
    assert exported["artifact"]["role"] == "selection-mask"
    assert (
        exported["artifact"]["sha256"]
        == hashlib.sha256(destination.read_bytes()).hexdigest()
    )
    assert json.loads(destination.read_text()) == ASYMMETRIC
    input_path = (
        str(Path("~") / os.path.relpath(destination, Path.home()))
        if spelling == "tilde"
        else str(destination)
    )
    assert Path(input_path).expanduser().samefile(destination)
    artifact = {"kind": "artifact", "path": input_path}
    validated = expect_success(
        "selection validate",
        canvas_request(selection=artifact, canvas=ASYMMETRIC["bounds"]),
    )
    assert validated["valid"] is True, validated
    restored = expect_success(
        "selection create", canvas_request(shape={"kind": "mask", "input": artifact})
    )
    assert restored["selection"] == ASYMMETRIC, restored
    preview = tmp_path / "mask.png"
    area = {"x": 9, "y": 19, "width": 6, "height": 4}
    rendered = expect_success(
        "selection preview",
        canvas_request(
            selection=artifact,
            canvas=area,
            destination={"path": str(preview), "if_exists": "fail"},
        ),
    )
    assert rendered["canvas"] == area
    assert rendered["artifact"]["role"] == "selection-preview"
    decoded = verify_png(preview.read_bytes(), preview)
    expected = pixels(["#...", "####"])
    assert decoded.rgba_bytes == b"".join(
        bytes([255] * 4) if (x, y) in expected else bytes(4)
        for y in range(19, 23)
        for x in range(9, 15)
    )
    assert set(tmp_path.iterdir()) == {destination, preview}


@pytest.mark.parametrize("operation", ["export", "preview"])
@pytest.mark.parametrize("value", [{"kind": "empty"}, ASYMMETRIC])
def test_artifact_empty_and_overwrite_failures_leave_no_staging_files(
    tmp_path, operation, value
) -> None:
    suffix = "png" if operation == "preview" else "json"
    target = tmp_path / f"selection.{suffix}"
    parameters = {"canvas": ASYMMETRIC["bounds"]} if operation == "preview" else {}
    result = expect_success(
        f"selection {operation}",
        canvas_request(
            selection=value,
            destination={"path": str(target), "if_exists": "fail"},
            **parameters,
        ),
    )
    assert result["selection"] == value
    original = target.read_bytes()
    outcome = run(
        f"selection {operation}",
        canvas_request(
            selection=value,
            destination={"path": str(target), "if_exists": "fail"},
            **parameters,
        ),
    )
    result = outcome.envelope
    assert outcome.returncode != 0 and result["code"] == "artifact_file_failed", result
    assert target.read_bytes() == original
    result = expect_success(
        f"selection {operation}",
        canvas_request(
            selection=value,
            destination={"path": str(target), "if_exists": "replace"},
            **parameters,
        ),
    )
    assert set(tmp_path.iterdir()) == {target}


def test_preview_refusal_does_not_publish_or_replace_existing_target(tmp_path) -> None:
    target = tmp_path / "preview.png"
    target.write_bytes(b"keep previous result")
    outcome = run(
        "selection preview",
        canvas_request(
            selection=ASYMMETRIC,
            canvas={"x": 11, "y": 20, "width": 3, "height": 2},
            destination={"path": str(target), "if_exists": "replace"},
        ),
    )
    result = outcome.envelope
    assert outcome.returncode != 0 and result["code"] == "selection_out_of_bounds", (
        result
    )
    assert target.read_bytes() == b"keep previous result"
    assert set(tmp_path.iterdir()) == {target}


def test_created_combined_transformed_selection_is_consumed_by_paint(tmp_path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 4,
            "height": 3,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    original = source.read_bytes()
    first = expect_success(
        "selection create",
        canvas_request(
            shape={
                "kind": "rectangle",
                "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
            }
        ),
    )
    second = expect_success(
        "selection combine",
        canvas_request(
            mode="subtract",
            left=first["selection"],
            right={
                "kind": "all",
                "rectangle": {"x": 1, "y": 0, "width": 1, "height": 1},
            },
        ),
    )
    third = expect_success(
        "selection transform",
        canvas_request(
            selection=second["selection"],
            canvas={"x": 0, "y": 0, "width": 4, "height": 3},
            transform={"kind": "translate", "offset": {"x": 2, "y": 1}},
        ),
    )
    red = {"kind": "rgba", "red": 255, "green": 0, "blue": 0, "alpha": 255}
    result = expect_success(
        "paint apply",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1], "frame_number": 1},
            "selection": third["selection"],
            "patch": {
                "coordinate_space": "image-pixel",
                "rectangle": {"x": 0, "y": 0, "width": 4, "height": 3},
                "runs": [{"x": 0, "y": y, "length": 4, "color": red} for y in range(3)],
            },
        },
    )
    assert result["pixels_written"] == 1
    assert result["pixels_skipped_by_selection"] == 11
    assert source.read_bytes() == original
    rows = expect_success(
        "image get",
        {
            "sprite_file": str(target),
            "source": {
                "kind": "individual",
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                "rectangle": {"x": 0, "y": 0, "width": 4, "height": 3},
            },
        },
    )["snapshot"]["rows"]
    actual = [
        [entry["color"] for entry in row for _ in range(entry["length"])]
        for row in rows
    ]
    assert {
        (x, y)
        for y, row in enumerate(actual)
        for x, c in enumerate(row)
        if c["alpha"] == 255
    } == {(2, 1)}


def test_native_coordinate_overflow_cannot_return_wrapped_success() -> None:
    area = {"x": 2**31, "y": 20, "width": 1, "height": 1}
    outcome = run(
        "selection create",
        canvas_request(shape={"kind": "rectangle", "rectangle": area}),
    )
    result = outcome.envelope
    assert outcome.returncode != 0, result
    assert result["code"] == "kernel_execution_failed"


@pytest.mark.parametrize("operation", ["grow", "shrink"])
def test_morphology_refuses_unrepresentable_native_footprint(operation) -> None:
    outcome = run(
        f"selection {operation}",
        canvas_request(
            selection={
                "kind": "all",
                "rectangle": {"x": 11, "y": 21, "width": 1, "height": 1},
            },
            canvas={"x": 10, "y": 20, "width": 3, "height": 3},
            radius=2**32,
            shape="square",
        ),
    )
    result = outcome.envelope
    assert outcome.returncode != 0 and result["code"] == "kernel_execution_failed", (
        result
    )
    assert result["diagnostics"]["exit_status"] == 0


def test_transform_tests_selected_coverage_not_the_placement_rectangle() -> None:
    result = expect_success(
        "selection transform",
        canvas_request(
            selection=ASYMMETRIC,
            canvas=ASYMMETRIC["bounds"],
            transform={"kind": "scale", "width": 8, "height": 1},
        ),
    )
    assert result["target_placement"] == {"x": 10, "y": 20, "width": 8, "height": 1}
    assert coverage(result["selection"]) == {(10, 20), (11, 20)}
