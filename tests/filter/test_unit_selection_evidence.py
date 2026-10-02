"""Selection evidence is consistent with an origin-based Sprite Canvas."""

from itertools import combinations, product

import pytest
from pydantic import TypeAdapter

from spa.authoring.raster.selection_evidence import matches_clipped_selection
from spa.contracts.raster import SelectionApplication

SELECTION = TypeAdapter(SelectionApplication)


def subsets(points):
    return [
        frozenset(subset)
        for size in range(len(points) + 1)
        for subset in combinations(points, size)
    ]


def selection_value(points, *, mask_rectangle=False):
    """Encode tiny, independently enumerated pixel sets as public wire values."""
    if not points:
        return SELECTION.validate_python({"kind": "empty"})
    left, top = min(x for x, _ in points), min(y for _, y in points)
    width = max(x for x, _ in points) + 1 - left
    height = max(y for _, y in points) + 1 - top
    bounds = {"x": left, "y": top, "width": width, "height": height}
    if len(points) == width * height and not mask_rectangle:
        return SELECTION.validate_python({"kind": "all", "rectangle": bounds})
    rows = []
    for y in sorted({y for _, y in points}):
        runs = []
        for x in sorted(x for x, row_y in points if row_y == y):
            if runs and runs[-1]["x"] + runs[-1]["length"] == x:
                runs[-1]["length"] += 1
            else:
                runs.append({"x": x, "length": 1})
        rows.append({"y": y, "runs": runs})
    return SELECTION.validate_python({"kind": "mask", "bounds": bounds, "rows": rows})


@pytest.mark.parametrize(
    "request_grid, observed_grid",
    [
        (list(product(range(-1, 2), repeat=2)), list(product(range(2), repeat=2))),
        ([(x, 0) for x in range(-1, 4)], [(x, 0) for x in range(4)]),
        ([(0, y) for y in range(-1, 4)], [(0, y) for y in range(4)]),
    ],
    ids=["two-dimensional", "row-holes", "column-holes"],
)
def test_matches_independent_pixel_set_oracle(request_grid, observed_grid):
    # Enumerate the actual set intersections for every distinct possible Canvas
    # in these finite scenes. This oracle does not use the guard's inferred area,
    # run containment, or pixel-count algorithm.
    canvases = [
        frozenset(product(range(width), range(height)))
        for width in range(1, max(x for x, _ in observed_grid) + 2)
        for height in range(1, max(y for _, y in observed_grid) + 2)
    ]
    observations = [
        (points, selection_value(points)) for points in subsets(observed_grid)
    ]
    for points in subsets(request_grid):
        possible = {points & canvas for canvas in canvases}
        requested = selection_value(points)
        forms = [requested]
        if requested.kind == "all":
            forms.append(selection_value(points, mask_rectangle=True))
        for request in forms:
            for observed_points, observed in observations:
                assert matches_clipped_selection(request, observed) == (
                    observed_points in possible
                ), (request, observed)


def test_equal_counts_do_not_hide_substituted_mask_pixels():
    requested = selection_value({(0, 0), (2, 0), (3, 1)})
    observed = selection_value({(1, 0), (2, 0), (3, 1)})
    assert not matches_clipped_selection(requested, observed)


@pytest.mark.parametrize("points", [{(-1, 0), (1, 0)}, {(0, -1), (0, 1)}])
def test_observed_negative_pixels_cannot_belong_to_a_sprite_canvas(points):
    value = selection_value(points)
    assert not matches_clipped_selection(value, value)


def test_no_pixel_or_row_expansion_for_large_rectangles():
    requested = SELECTION.validate_python(
        {
            "kind": "all",
            "rectangle": {"x": -1, "y": -1, "width": 10001, "height": 10001},
        }
    )
    observed = SELECTION.validate_python(
        {"kind": "all", "rectangle": {"x": 0, "y": 0, "width": 10000, "height": 10000}}
    )
    assert matches_clipped_selection(requested, observed)
