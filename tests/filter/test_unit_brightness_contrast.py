"""Brightness/Contrast requests require explicit, applicable native choices."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from spa.authoring.raster.filter import BrightnessContrastRequest

SELECTED = {
    "kind": "selected",
    "layers": [{"layer_path": [1]}],
    "frame_numbers": [1, 2],
}
RGB = {"kind": "components", "names": ["red", "blue"]}
APPLICATIONS = [
    {
        "kind": "pixels",
        "color_mode": "rgb",
        "channels": RGB,
        "cels_target": SELECTED,
        "selection": {"kind": "empty"},
    },
    {
        "kind": "pixels",
        "color_mode": "grayscale",
        "channels": {"kind": "components", "names": ["gray"]},
        "cels_target": {"kind": "all"},
    },
    {
        "kind": "pixels",
        "color_mode": "indexed",
        "channels": RGB,
        "cels_target": SELECTED,
        "palette_frame_number": 1,
    },
    {
        "kind": "indexed-palette-entries",
        "palette_frame_number": 1,
        "entries": {"kind": "selected", "indexes": [0, 2]},
        "channels": RGB,
    },
    {
        "kind": "rgb-palette-colors",
        "palette_frame_number": 1,
        "indexes": [0, 2],
        "channels": RGB,
        "cels_target": SELECTED,
    },
]
SCHEMA = Draft202012Validator(BrightnessContrastRequest.model_json_schema())


@pytest.mark.parametrize(
    "application",
    [app for app in APPLICATIONS if app["kind"] != "indexed-palette-entries"],
)
def test_manual_tileset_mode_is_explicit_for_pixel_applications(application):
    data = payload({**application, "tileset_mode": "manual"})
    assert (
        BrightnessContrastRequest.model_validate(data).application.tileset_mode
        == "manual"
    )
    SCHEMA.validate(data)


@pytest.mark.parametrize("value", ["auto", "stack", "Manual", 0, True])
def test_other_tileset_modes_are_not_public_choices(value):
    data = payload({**APPLICATIONS[0], "tileset_mode": value})
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)
    assert not SCHEMA.is_valid(data)


def test_palette_only_has_no_tileset_mode():
    data = payload({**APPLICATIONS[3], "tileset_mode": "manual"})
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)
    assert not SCHEMA.is_valid(data)


def payload(application=None):
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "brightness": 0,
        "contrast": 0,
        "application": deepcopy(
            APPLICATIONS[0] if application is None else application
        ),
    }


@pytest.mark.parametrize("application", APPLICATIONS)
def test_all_five_explicit_applications_accept_zero_adjustment(application):
    data = payload(application)
    request = BrightnessContrastRequest.model_validate(data)
    assert request.brightness == request.contrast == 0
    assert request.application.model_dump(exclude_none=True) == application
    SCHEMA.validate(data)


def test_palette_only_all_entries_has_no_cel_target():
    application = deepcopy(APPLICATIONS[3])
    application["entries"] = {"kind": "all"}
    request = BrightnessContrastRequest.model_validate(payload(application))
    assert request.application.entries.kind == "all"


@pytest.mark.parametrize(
    "field",
    [
        "source_sprite_file",
        "target_sprite_file",
        "in_place",
        "overwrite",
        "brightness",
        "contrast",
        "application",
    ],
)
def test_required_choices_have_no_ambient_defaults(field):
    data = payload()
    del data[field]
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)
    assert not SCHEMA.is_valid(data)


@pytest.mark.parametrize("field", ["brightness", "contrast"])
@pytest.mark.parametrize(
    "value", [True, "0", 0.5, float("inf"), float("nan"), -101, 101]
)
def test_adjustments_reject_coercion_nonfinite_and_out_of_range(field, value):
    data = payload()
    data[field] = value
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)
    assert not SCHEMA.is_valid(data)


@pytest.mark.parametrize("field", ["brightness", "contrast"])
@pytest.mark.parametrize("value", [-100, 100])
def test_adjustment_boundaries_are_valid(field, value):
    data = payload()
    data[field] = value
    assert getattr(BrightnessContrastRequest.model_validate(data), field) == value
    SCHEMA.validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sprite_file", "source.png"),
        ("target_sprite_file", "target.ase"),
        ("source_sprite_file", ""),
        ("in_place", 1),
        ("overwrite", "false"),
        ("tiled_mode", "both"),
        ("gamma", 1),
    ],
)
def test_invalid_paths_flags_and_custom_tuning_are_rejected(field, value):
    data = payload()
    data[field] = value
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)


def test_in_place_requires_explicit_overwrite_permission():
    data = payload()
    data.update(target_sprite_file="source.aseprite", in_place=True)
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)
    data["overwrite"] = True
    assert BrightnessContrastRequest.model_validate(data).in_place is True


@pytest.mark.parametrize("application", APPLICATIONS)
@pytest.mark.parametrize(
    "channels",
    [
        {"kind": "index"},
        {"kind": "components", "names": ["alpha"]},
        {"kind": "components", "names": []},
        {"kind": "components", "names": ["red", "red"]},
        {"kind": "components", "names": ["unknown"]},
    ],
)
def test_unsupported_or_ambiguous_channels_fail_every_branch(application, channels):
    data = payload(application)
    data["application"]["channels"] = channels
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cels_target", {"kind": "all", "frame_numbers": [1]}),
        ("cels_target", {"kind": "selected", "layers": [], "frame_numbers": [1]}),
        (
            "cels_target",
            {
                "kind": "selected",
                "layers": [{"layer_path": [1]}],
                "frame_numbers": [1, 1],
            },
        ),
        (
            "cels_target",
            {
                "kind": "selected",
                "layers": [{"layer_path": [1]}] * 2,
                "frame_numbers": [1],
            },
        ),
        (
            "cels_target",
            {"kind": "selected", "layers": [{"layer_path": [0]}], "frame_numbers": [1]},
        ),
        (
            "cels_target",
            {
                "kind": "selected",
                "layers": [{"layer_path": [1]}],
                "frame_numbers": [True],
            },
        ),
        ("channels", {"kind": "components", "names": ["gray"]}),
        ("palette_frame_number", 1),
        ("entries", {"kind": "all"}),
        ("selection", {"kind": "all"}),
    ],
)
def test_pixel_target_and_application_conflicts_are_rejected(field, value):
    data = payload()
    data["application"][field] = value
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)


@pytest.mark.parametrize(
    "branch,field",
    [
        (0, "color_mode"),
        (0, "cels_target"),
        (0, "channels"),
        (2, "palette_frame_number"),
        (3, "entries"),
        (3, "palette_frame_number"),
        (4, "indexes"),
        (4, "cels_target"),
    ],
)
def test_branch_specific_required_choices_cannot_be_omitted(branch, field):
    data = payload(APPLICATIONS[branch])
    del data["application"][field]
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)
    assert not SCHEMA.is_valid(data)


@pytest.mark.parametrize("branch", [3, 4])
@pytest.mark.parametrize("indexes", [[], [0, 0], [-1], [True], ["0"]])
def test_palette_indexes_are_nonempty_unique_strict_zero_based(branch, indexes):
    data = payload(APPLICATIONS[branch])
    target = data["application"]["entries"] if branch == 3 else data["application"]
    target["indexes"] = indexes
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cels_target", {"kind": "all"}),
        ("selection", {"kind": "empty"}),
        ("color_mode", "indexed"),
        ("indexes", [0]),
        ("palette_frame_number", 0),
    ],
)
def test_palette_only_rejects_pixel_destination_and_invalid_basis(field, value):
    data = payload(APPLICATIONS[3])
    data["application"][field] = value
    with pytest.raises(ValidationError):
        BrightnessContrastRequest.model_validate(data)
