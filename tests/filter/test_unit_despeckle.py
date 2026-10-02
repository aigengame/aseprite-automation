"""Despeckle admits only its bounded, explicit native request."""

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from spa.authoring.raster.despeckle import DespeckleRequest


def payload():
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "width": 3,
        "height": 3,
        "tiled_mode": "none",
        "pixels": {
            "color_mode": "rgb",
            "channels": {"kind": "components", "names": ["red"]},
            "cels_target": {"kind": "all"},
        },
    }


def rejected(data):
    with pytest.raises(ValidationError):
        DespeckleRequest.model_validate(data)
    assert not Draft202012Validator(DespeckleRequest.model_json_schema()).is_valid(data)


@pytest.mark.parametrize("dimension", ["width", "height"])
@pytest.mark.parametrize("value", [1, 2, 3, 100])
def test_odd_even_and_boundary_dimensions_are_explicit(dimension, value):
    data = payload()
    data[dimension] = value
    assert getattr(DespeckleRequest.model_validate(data), dimension) == value
    Draft202012Validator(DespeckleRequest.model_json_schema()).validate(data)


@pytest.mark.parametrize("dimension", ["width", "height"])
@pytest.mark.parametrize("value", [None, 0, -1, 101, 2.5, True, "3"])
def test_invalid_dimensions_are_not_clamped(dimension, value):
    data = payload()
    data[dimension] = value
    rejected(data)


@pytest.mark.parametrize("field", ["width", "height", "tiled_mode", "pixels"])
def test_required_intent_cannot_be_omitted(field):
    data = payload()
    del data[field]
    rejected(data)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_dimension_fails_before_invocation(value):
    data = payload()
    data["width"] = value
    with pytest.raises(ValidationError):
        DespeckleRequest.model_validate(data)


@pytest.mark.parametrize(
    "mode,names",
    [
        ("rgb", ["red", "green", "blue", "alpha"]),
        ("grayscale", ["gray", "alpha"]),
        ("indexed", ["green", "alpha"]),
    ],
)
def test_channels_and_palette_basis_follow_color_mode(mode, names):
    data = payload()
    data["pixels"].update(
        color_mode=mode, channels={"kind": "components", "names": names}
    )
    if mode == "indexed":
        data["pixels"]["palette_frame_number"] = 1
    request = DespeckleRequest.model_validate(data)
    assert request.pixels.channels.names == names
    Draft202012Validator(DespeckleRequest.model_json_schema()).validate(data)
    if mode == "indexed":
        data["pixels"]["channels"] = {"kind": "index"}
        assert DespeckleRequest.model_validate(data).pixels.channels.kind == "index"
        del data["pixels"]["palette_frame_number"]
    else:
        data["pixels"]["channels"] = {
            "kind": "components",
            "names": ["gray" if mode == "rgb" else "red"],
        }
    rejected(data)


@pytest.mark.parametrize(
    "channels",
    [
        {"kind": "index"},
        {"kind": "components", "names": []},
        {"kind": "components", "names": ["red", "red"]},
        {"kind": "components", "names": ["RED"]},
        {"kind": "components", "names": [1]},
    ],
)
def test_invalid_or_inapplicable_channels_are_rejected(channels):
    data = payload()
    data["pixels"]["channels"] = channels
    rejected(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("application", {}),
        ("strength", 50),
        ("radius", 3),
        ("percentile", 50),
        ("iterations", 2),
    ],
)
def test_unrequested_filter_inputs_are_absent(field, value):
    data = payload()
    data[field] = value
    rejected(data)


def test_unknown_tiled_mode_and_tilemap_extension_are_not_admitted():
    data = payload()
    data["tiled_mode"] = "X"
    rejected(data)
    data = payload()
    data["pixels"]["tileset_mode"] = "manual"
    rejected(data)
    data = payload()
    data["pixels"]["channels"] = {"kind": "index", "names": ["green"]}
    data["pixels"].update(color_mode="indexed", palette_frame_number=1)
    rejected(data)
