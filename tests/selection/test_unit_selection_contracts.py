"""Invalid Selection requests stay invalid even when coverage is empty."""

import pytest
from pydantic import ValidationError

from spa.selection import SelectionMorphologyRequest, SelectionTransformRequest


@pytest.mark.parametrize(
    "transform",
    [
        {"kind": "scale", "width": 0, "height": 1},
        {"kind": "scale", "width": 1.5, "height": 2},
        {"kind": "rotate", "angle": 45},
        {"kind": "flip", "axis": "diagonal"},
        {"kind": "translate", "offset": {"x": 0.5, "y": 1}},
    ],
)
def test_empty_does_not_bypass_transform_parameters(transform) -> None:
    with pytest.raises(ValidationError):
        SelectionTransformRequest.model_validate(
            {
                "coordinate_space": "canvas-pixel",
                "selection": {"kind": "empty"},
                "canvas": {"x": 0, "y": 0, "width": 4, "height": 3},
                "transform": transform,
            }
        )


@pytest.mark.parametrize(
    "options",
    [
        {"radius": 0, "shape": "circle"},
        {"radius": 1, "shape": "disk"},
        {"radius": True, "shape": "square"},
    ],
)
def test_empty_does_not_bypass_morphology_parameters(options) -> None:
    with pytest.raises(ValidationError):
        SelectionMorphologyRequest.model_validate(
            {
                "coordinate_space": "canvas-pixel",
                "selection": {"kind": "empty"},
                "canvas": {"x": 0, "y": 0, "width": 4, "height": 3},
                **options,
            }
        )
