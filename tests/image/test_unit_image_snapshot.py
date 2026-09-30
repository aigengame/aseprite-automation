"""Public Snapshot contracts reject ambiguous or incomplete complete images."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from spa.authoring.raster.image_snapshot import ImageGetRequest, ImageReplaceRequest
from spa.contracts.raster import PixelRegionSnapshot


def _snapshot() -> dict:
    return {
        "coordinate_space": "image-pixel",
        "color_mode": "rgb",
        "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
        "rows": [
            [
                {
                    "length": 2,
                    "color": {
                        "kind": "rgba",
                        "red": 1,
                        "green": 2,
                        "blue": 3,
                        "alpha": 0,
                    },
                }
            ]
        ],
    }


@pytest.mark.parametrize(
    "defect",
    [
        "missing-row",
        "short-row",
        "extra-pixel",
        "adjacent",
        "mode",
        "packed",
        "origin",
        "channel",
        "space",
    ],
)
def test_noncanonical_snapshot_is_rejected(defect: str) -> None:
    value = _snapshot()
    run = value["rows"][0][0]
    if defect == "missing-row":
        value["rows"] = []
    elif defect == "short-row":
        run["length"] = 1
    elif defect == "extra-pixel":
        run["length"] = 3
    elif defect == "adjacent":
        run["length"] = 1
        value["rows"][0].append(deepcopy(run))
    elif defect == "mode":
        value["color_mode"] = "indexed"
    elif defect == "packed":
        run["color"] = 0xFF0000FF
    elif defect == "origin":
        value["rectangle"]["x"] = 1
    elif defect == "channel":
        run["color"]["red"] = 256
    else:
        value["coordinate_space"] = "canvas-pixel"
    with pytest.raises(ValidationError):
        PixelRegionSnapshot.model_validate(value)


def test_above_inline_limit_requires_explicit_artifact_transport() -> None:
    request = {
        "sprite_file": "source.aseprite",
        "source": {
            "kind": "individual",
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "rectangle": {"x": 0, "y": 0, "width": 4097, "height": 1},
        },
    }
    with pytest.raises(ValidationError, match="snapshot_destination"):
        ImageGetRequest.model_validate(request)
    request["snapshot_destination"] = {"path": "pixels.json", "if_exists": "fail"}
    assert ImageGetRequest.model_validate(request).snapshot_destination is not None
    value = _snapshot()
    value["rectangle"]["width"] = value["rows"][0][0]["length"] = 4097
    with pytest.raises(ValidationError, match="Artifact input"):
        ImageReplaceRequest.model_validate(
            {
                "source_sprite_file": "source.aseprite",
                "target_sprite_file": "target.aseprite",
                "in_place": False,
                "overwrite": False,
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                "input": {"kind": "inline", "snapshot": value},
            }
        )


@pytest.mark.parametrize("choice", [None, "indexed", "rgba", "automatic"])
def test_composite_requires_an_explicit_supported_output_choice(
    choice: str | None,
) -> None:
    source = {
        "kind": "composite",
        "frame_number": 1,
        "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
        "layer_composition": {"mode": "visible"},
    }
    if choice is not None:
        source["output_color_mode"] = choice
    with pytest.raises(ValidationError, match="output_color_mode"):
        ImageGetRequest.model_validate(
            {"sprite_file": "source.aseprite", "source": source}
        )
