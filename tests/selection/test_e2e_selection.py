"""Explicit Selection values through the public CLI and real Aseprite."""

import json
import os

import pytest

from tests.support import spa

pytestmark = pytest.mark.e2e


def selection(operation: str, **values) -> tuple[int, dict]:
    run = spa(
        "selection",
        operation,
        "--input-json",
        json.dumps(
            {
                "coordinate_space": "canvas-pixel",
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                **values,
            }
        ),
    )
    return run.returncode, json.loads(run.stdout)


def test_create_rectangle_retains_absolute_canvas_coordinates() -> None:
    rectangle = {"x": -3, "y": 7, "width": 4, "height": 2}
    code, result = selection(
        "create", shape={"kind": "rectangle", "rectangle": rectangle}
    )

    assert code == 0, result
    assert result["selection"] == {"kind": "all", "rectangle": rectangle}
    assert result["bounds"] == rectangle
    assert result["pixel_count"] == 8
    assert result["coordinate_space"] == "canvas-pixel"


@pytest.mark.parametrize(("width", "height"), [(1, 1), (1, 5), (5, 1)])
def test_degenerate_ellipse_uses_inclusive_native_endpoints(width, height) -> None:
    bounds = {"x": 11, "y": -8, "width": width, "height": height}
    code, result = selection("create", shape={"kind": "ellipse", "bounds": bounds})
    assert code == 0, result
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
    code, result = selection("combine", mode=mode, left=left, right=right)
    assert code == 0, result
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
    code, created = selection("create", shape={"kind": "mask", "input": ASYMMETRIC})
    assert code == 0, created
    assert created["selection"] == ASYMMETRIC
    code, inverted = selection(
        "invert", selection=created["selection"], canvas=ASYMMETRIC["bounds"]
    )
    assert code == 0, inverted
    assert coverage(inverted["selection"]) == {(11, 20), (12, 20), (13, 20)}


@pytest.mark.parametrize(
    "value", [{"kind": "empty"}, {"kind": "all", "rectangle": ASYMMETRIC["bounds"]}]
)
def test_invert_empty_and_full(value) -> None:
    code, result = selection("invert", selection=value, canvas=ASYMMETRIC["bounds"])
    assert code == 0, result
    assert result["pixel_count"] == (8 if value["kind"] == "empty" else 0)
    assert result["selection"]["kind"] == (
        "all" if value["kind"] == "empty" else "empty"
    )
