"""Public transform contracts reject ambiguous or lossy native requests."""

import pytest
from pydantic import ValidationError

from spa.image import ImageCanvasResizeRequest, ImageCropRequest

COMMON = {
    "source_sprite_file": "source.aseprite",
    "target_sprite_file": "target.aseprite",
    "in_place": False,
    "overwrite": False,
    "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
    "coordinate_space": "image-pixel",
    "position_policy": "keep_cel_position",
}
CROP = {**COMMON, "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1}}
CANVAS = {
    **COMMON,
    "width": 2,
    "height": 2,
    "offset": {"x": 0, "y": 0},
    "fill": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 0},
}


@pytest.mark.parametrize(
    ("model", "payload", "changes"),
    [
        (
            ImageCropRequest,
            CROP,
            {"rectangle": {"x": 0, "y": 0, "width": 0, "height": 1}},
        ),
        (
            ImageCropRequest,
            CROP,
            {"rectangle": {"x": 0.5, "y": 0, "width": 1, "height": 1}},
        ),
        (
            ImageCropRequest,
            CROP,
            {"rectangle": {"x": 2**31, "y": 0, "width": 1, "height": 1}},
        ),
        (ImageCropRequest, CROP, {"coordinate_space": "canvas-pixel"}),
        (ImageCropRequest, CROP, {"position_policy": "preserve_source_canvas"}),
        (ImageCropRequest, CROP, {"target": {"image_id": 1}}),
        (ImageCanvasResizeRequest, CANVAS, {"width": True}),
        (ImageCanvasResizeRequest, CANVAS, {"width": 65536}),
        (ImageCanvasResizeRequest, CANVAS, {"height": 0}),
        (ImageCanvasResizeRequest, CANVAS, {"offset": {"x": 0.5, "y": 0}}),
        (ImageCanvasResizeRequest, CANVAS, {"offset": {"x": -(2**31) - 1, "y": 0}}),
        (
            ImageCanvasResizeRequest,
            CANVAS,
            {"fill": {"kind": "palette-index", "index": 1.0}},
        ),
        (
            ImageCanvasResizeRequest,
            CANVAS,
            {"fill": {"kind": "palette-index", "index": 256}},
        ),
        (
            ImageCanvasResizeRequest,
            CANVAS,
            {"position_policy": "preserve_canvas_pixels"},
        ),
        (ImageCanvasResizeRequest, CANVAS, {"in_place": True, "overwrite": False}),
    ],
)
def test_invalid_intent_is_rejected(model, payload: dict, changes: dict) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({**payload, **changes})


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (ImageCropRequest, CROP, "position_policy"),
        (ImageCanvasResizeRequest, CANVAS, "position_policy"),
        (ImageCanvasResizeRequest, CANVAS, "fill"),
        (ImageCanvasResizeRequest, CANVAS, "offset"),
    ],
)
def test_required_intent_has_no_implicit_default(
    model, payload: dict, field: str
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(
            {key: value for key, value in payload.items() if key != field}
        )
