"""Static coverage checks for Selection evidence applied to a Sprite Canvas."""

from spa.contracts.raster import (
    AllSelection,
    EmptySelection,
    MaskSelection,
    PositiveRectangle,
    SelectionApplication,
)


def _covered_pixels(value: SelectionApplication, area: PositiveRectangle) -> int:
    """Count declared coverage inside an area without expanding pixels or rows."""
    right, bottom = area.x + area.width, area.y + area.height
    if isinstance(value, EmptySelection):
        return 0
    if isinstance(value, AllSelection):
        rect = value.rectangle
        return max(0, min(right, rect.x + rect.width) - max(area.x, rect.x)) * max(
            0, min(bottom, rect.y + rect.height) - max(area.y, rect.y)
        )
    return sum(
        max(0, min(right, run.x + run.length) - max(area.x, run.x))
        for row in value.rows
        if area.y <= row.y < bottom
        for run in row.runs
    )


def _mask_contains(requested: MaskSelection, observed: MaskSelection) -> bool:
    rows = {row.y: row.runs for row in requested.rows}
    for row in observed.rows:
        runs = iter(rows.get(row.y, ()))
        allowed = next(runs, None)
        for run in row.runs:
            while allowed is not None and allowed.x + allowed.length <= run.x:
                allowed = next(runs, None)
            if (
                allowed is None
                or run.x < allowed.x
                or run.x + run.length > allowed.x + allowed.length
            ):
                return False
    return True


def matches_clipped_selection(
    requested: SelectionApplication | None, observed: SelectionApplication | None
) -> bool:
    """Reject coverage that no positive, origin-based Sprite Canvas can explain.

    Canvas dimensions are not in this evidence. A nonempty observation guarantees
    that the Canvas contains the area from its origin to the observed right/bottom
    edges; an empty observation still guarantees pixel (0, 0). In that area, the
    observation must contain every requested pixel and no unrequested pixel.

    This checks wire facts, not the actual Canvas dimensions or native execution.
    The Kernel still materializes, clips, and normalizes the native Selection.
    """
    if requested is None:
        return (
            isinstance(observed, AllSelection)
            and observed.rectangle.x == 0
            and observed.rectangle.y == 0
        )
    if observed is None:
        return False
    if isinstance(observed, EmptySelection):
        return (
            _covered_pixels(requested, PositiveRectangle(x=0, y=0, width=1, height=1))
            == 0
        )

    bounds = (
        observed.rectangle if isinstance(observed, AllSelection) else observed.bounds
    )
    if bounds.x < 0 or bounds.y < 0:
        return False
    guaranteed_canvas = PositiveRectangle(
        x=0, y=0, width=bounds.x + bounds.width, height=bounds.y + bounds.height
    )
    observed_count = _covered_pixels(observed, bounds)
    if _covered_pixels(requested, guaranteed_canvas) != observed_count:
        return False
    if isinstance(observed, AllSelection):
        return _covered_pixels(requested, bounds) == observed_count
    # A native clipped rectangle cannot become a sparse Mask.
    return isinstance(requested, MaskSelection) and _mask_contains(requested, observed)
