"""Pixel-only Filter contracts agree with their public JSON schemas."""

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from spa.authoring.raster.invert_outline import InvertColorRequest, OutlineRequest


def request_data(outline=False, mode="rgb"):
    data = {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "color_mode": mode,
        "channels": {
            "kind": "components",
            "names": ["gray" if mode == "grayscale" else "red"],
        },
        "cels_target": {"kind": "all"},
    }
    if mode == "indexed":
        data.update(palette_frame_number=1, channels={"kind": "index"})
    if outline:
        colors = {
            "rgb": {"kind": "rgba", "red": 1, "green": 2, "blue": 3, "alpha": 255},
            "grayscale": {"kind": "grayscale", "gray": 1, "alpha": 255},
            "indexed": {"kind": "palette-index", "index": 1},
        }
        data.update(
            place="outside",
            outline_color=colors[mode],
            background_color=colors[mode],
            matrix={"kind": "preset", "name": "circle"},
            tiled_mode="none",
        )
    return data


@pytest.mark.parametrize("model", [InvertColorRequest, OutlineRequest])
@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_pixel_only_request_has_explicit_mode_channels_and_targets(model, mode):
    data = request_data(model is OutlineRequest, mode)
    assert model.model_validate(data).color_mode == mode
    Draft202012Validator(model.model_json_schema()).validate(data)
    for field in ["application", "amount", "tileset_mode"]:
        with pytest.raises(ValidationError):
            model.model_validate({**data, field: "invalid"})


@pytest.mark.parametrize("model", [InvertColorRequest, OutlineRequest])
@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("channels", {"kind": "components", "names": []}),
        ("channels", {"kind": "components", "names": ["alpha", "alpha"]}),
        ("channels", {"kind": "components", "names": ["unknown"]}),
        ("channels", {"kind": "index", "names": ["red"]}),
        (
            "cels_target",
            {"kind": "selected", "layers": [{"layer_path": [1]}], "frame_numbers": []},
        ),
        ("palette_frame_number", 0),
        ("palette_frame_number", True),
    ],
)
def test_invalid_shared_choices_fail_runtime_and_schema(model, mode, field, value):
    data = {**request_data(model is OutlineRequest, mode), field: value}
    with pytest.raises(ValidationError):
        model.model_validate(data)
    assert not Draft202012Validator(model.model_json_schema()).is_valid(data)


@pytest.mark.parametrize("model", [InvertColorRequest, OutlineRequest])
@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_mode_constraints_and_required_choices_match_schema(model, mode):
    data = request_data(model is OutlineRequest, mode)
    invalids = [
        {**data, "palette_frame_number": None if mode == "indexed" else 1},
        {
            **data,
            "channels": {
                "kind": "components",
                "names": ["red" if mode == "grayscale" else "gray"],
            },
        },
    ]
    if mode != "indexed":
        invalids.append({**data, "channels": {"kind": "index"}})
    for field in data:
        invalids.append({k: v for k, v in data.items() if k != field})
    for invalid in invalids:
        with pytest.raises(ValidationError):
            model.model_validate(invalid)
        assert not Draft202012Validator(model.model_json_schema()).is_valid(invalid), (
            invalid
        )


@pytest.mark.parametrize("neighbors", [[], ["top", "top"], ["center"], [0], [True]])
def test_custom_matrix_rejects_empty_duplicate_center_and_raw_bits(neighbors):
    data = {**request_data(True), "matrix": {"kind": "custom", "neighbors": neighbors}}
    with pytest.raises(ValidationError):
        OutlineRequest.model_validate(data)
    assert not Draft202012Validator(OutlineRequest.model_json_schema()).is_valid(data)


@pytest.mark.parametrize("name", ["none", "circle", "square", "horizontal", "vertical"])
def test_outline_presets_are_explicit_including_empty_neighborhood(name):
    data = {**request_data(True), "matrix": {"kind": "preset", "name": name}}
    OutlineRequest.model_validate(data)
    Draft202012Validator(OutlineRequest.model_json_schema()).validate(data)


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("field", ["outline_color", "background_color"])
def test_outline_colors_match_mode(mode, field):
    data = request_data(True, mode)
    data[field] = request_data(True, "rgb" if mode != "rgb" else "indexed")[field]
    with pytest.raises(ValidationError):
        OutlineRequest.model_validate(data)
    assert not Draft202012Validator(OutlineRequest.model_json_schema()).is_valid(data)


@pytest.mark.parametrize("model", [InvertColorRequest, OutlineRequest])
def test_channels_include_each_demonstrated_component(model):
    for mode, names in [
        ("rgb", ["red", "green", "blue", "alpha"]),
        ("grayscale", ["gray", "alpha"]),
        ("indexed", ["red", "green", "blue", "alpha"]),
    ]:
        for selected in [[name] for name in names] + [names]:
            data = {
                **request_data(model is OutlineRequest, mode),
                "channels": {"kind": "components", "names": selected},
            }
            model.model_validate(data)
            Draft202012Validator(model.model_json_schema()).validate(data)


def test_pixel_filters_do_not_register_operation_plan_steps():
    from spa.application.surface import OPERATIONS

    for name in ["filter invert-color", "filter outline"]:
        descriptor = next(item for item in OPERATIONS if item.name == name)
        assert descriptor.plan_eligible is False
