"""Issue #36 governs adjustment forms by selected color and Alpha Channels."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from spa.authoring.raster.hue_saturation import HueSaturationRequest

APPLICATIONS = [
    {
        "kind": "pixels",
        "color_mode": "rgb",
        "channels": {"kind": "components", "names": ["red", "green", "blue"]},
        "cels_target": {"kind": "all"},
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
        "channels": {"kind": "components", "names": ["red"]},
        "cels_target": {"kind": "all"},
        "palette_frame_number": 1,
    },
    {
        "kind": "indexed-palette-entries",
        "palette_frame_number": 1,
        "entries": {"kind": "selected", "indexes": [0, 2]},
        "channels": {"kind": "components", "names": ["blue"]},
    },
    {
        "kind": "rgb-palette-colors",
        "palette_frame_number": 1,
        "indexes": [0, 2],
        "channels": {"kind": "components", "names": ["green"]},
        "cels_target": {"kind": "all"},
    },
]
MODES = ["hsl-multiply", "hsl-add", "hsv-multiply", "hsv-add"]
SCHEMA = Draft202012Validator(HueSaturationRequest.model_json_schema())


def adjustment(mode):
    if mode == "grayscale":
        return {"mode": mode, "lightness": 0}
    return {
        "mode": mode,
        "hue": 0,
        "saturation": 0,
        "value" if mode.startswith("hsv") else "lightness": 0,
    }


def payload(branch=0, mode="hsl-multiply"):
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "application": deepcopy(APPLICATIONS[branch]),
        "adjustment": adjustment("grayscale" if branch == 1 else mode),
    }


def assert_rejected(data):
    with pytest.raises(ValidationError):
        HueSaturationRequest.model_validate(data)
    assert not SCHEMA.is_valid(data)


@pytest.mark.parametrize("branch", range(5))
@pytest.mark.parametrize("mode", MODES)
def test_all_applications_accept_applicable_zero_adjustment(branch, mode):
    data = payload(branch, mode)
    request = HueSaturationRequest.model_validate(data)
    assert request.application.model_dump(exclude_none=True) == data["application"]
    assert request.adjustment.model_dump() == data["adjustment"]
    SCHEMA.validate(data)


@pytest.mark.parametrize("branch", range(5))
@pytest.mark.parametrize("with_color", [False, True])
def test_alpha_is_independent_and_zero_is_valid(branch, with_color):
    data = payload(branch)
    names = data["application"]["channels"]["names"]
    data["application"]["channels"]["names"] = (
        [*names, "alpha"] if with_color else ["alpha"]
    )
    if not with_color:
        del data["adjustment"]
    data["alpha"] = 0
    assert HueSaturationRequest.model_validate(data).alpha == 0
    SCHEMA.validate(data)
    del data["alpha"]
    assert_rejected(data)


@pytest.mark.parametrize("branch", range(5))
def test_exact_channel_governance(branch):
    data = payload(branch)
    data["alpha"] = 0
    assert_rejected(data)
    del data["alpha"]
    del data["adjustment"]
    assert_rejected(data)
    data["application"]["channels"]["names"] = ["alpha"]
    data["alpha"] = 0
    data["adjustment"] = adjustment("grayscale" if branch == 1 else "hsl-add")
    assert_rejected(data)


@pytest.mark.parametrize("branch", range(5))
@pytest.mark.parametrize(
    "channels",
    [
        {"kind": "index"},
        {"kind": "components", "names": []},
        {"kind": "components", "names": ["alpha", "alpha"]},
        {"kind": "components", "names": ["unknown"]},
    ],
)
def test_invalid_channels_reject_in_runtime_and_schema(branch, channels):
    data = payload(branch)
    data["application"]["channels"] = channels
    assert_rejected(data)


@pytest.mark.parametrize("branch", range(5))
def test_color_component_and_form_must_match_application(branch):
    data = payload(branch)
    data["application"]["channels"]["names"] = ["red" if branch == 1 else "gray"]
    assert_rejected(data)
    data = payload(branch)
    data["adjustment"] = adjustment("hsv-add" if branch == 1 else "grayscale")
    assert_rejected(data)


@pytest.mark.parametrize("mode", [*MODES, "grayscale"])
def test_form_requires_its_components_and_forbids_other_components(mode):
    data = payload(1 if mode == "grayscale" else 0, mode)
    for field in set(data["adjustment"]) - {"mode"}:
        incomplete = deepcopy(data)
        del incomplete["adjustment"][field]
        assert_rejected(incomplete)
    invalid = deepcopy(data)
    invalid["adjustment"][
        "value" if "lightness" in data["adjustment"] else "lightness"
    ] = 0
    assert_rejected(invalid)
    if mode == "grayscale":
        for field in ["hue", "saturation"]:
            invalid = deepcopy(data)
            invalid["adjustment"][field] = 0
            assert_rejected(invalid)


@pytest.mark.parametrize("mode", ["hsl", "hsv", "hsl_add", "hsv_add", "unknown", None])
def test_unknown_and_native_only_mode_names_are_invalid(mode):
    data = payload()
    data["adjustment"]["mode"] = mode
    assert_rejected(data)


@pytest.mark.parametrize(
    "mode,field,limit",
    [
        ("hsl-multiply", "hue", 180),
        ("hsl-add", "saturation", 100),
        ("hsl-add", "lightness", 100),
        ("hsv-multiply", "hue", 180),
        ("hsv-add", "saturation", 100),
        ("hsv-add", "value", 100),
        ("grayscale", "lightness", 100),
        (None, "alpha", 100),
    ],
)
def test_adjustment_integer_boundaries_and_invalid_values(mode, field, limit):
    data = payload(1 if mode == "grayscale" else 0, mode or "hsl-multiply")
    if mode is None:
        data["application"]["channels"]["names"] = ["alpha"]
        del data["adjustment"]
    target = data if mode is None else data["adjustment"]
    for value in [-limit, limit]:
        target[field] = value
        HueSaturationRequest.model_validate(data)
        SCHEMA.validate(data)
    for value in [True, "0", 0.5, float("inf"), float("nan"), -limit - 1, limit + 1]:
        target[field] = value
        assert_rejected(data)


@pytest.mark.parametrize(
    "field", ["tiled_mode", "color", "matrix", "transfer", "index", "mode"]
)
def test_request_forbids_uncontracted_tuning(field):
    data = payload()
    data[field] = 0
    assert_rejected(data)


@pytest.mark.parametrize(
    "field",
    [
        "source_sprite_file",
        "target_sprite_file",
        "in_place",
        "overwrite",
        "application",
    ],
)
def test_shared_explicit_choices_remain_required(field):
    data = payload()
    del data[field]
    assert_rejected(data)


@pytest.mark.parametrize("branch", [3, 4])
@pytest.mark.parametrize("indexes", [[], [0, 0], [-1], [True], ["0"]])
def test_palette_entry_indexes_are_unique_strict_zero_based(branch, indexes):
    data = payload(branch)
    target = data["application"]["entries"] if branch == 3 else data["application"]
    target["indexes"] = indexes
    assert_rejected(data)


@pytest.mark.parametrize("branch", range(5))
def test_extra_application_fields_and_unknown_modes_fail(branch):
    data = payload(branch)
    data["application"]["tiled_mode"] = "both"
    assert_rejected(data)
    data = payload(branch)
    if branch < 3:
        data["application"]["color_mode"] = "unknown"
    else:
        data["application"]["kind"] = "grayscale-palette-colors"
    assert_rejected(data)


@pytest.mark.parametrize("names", [["red"], ["green"], ["blue"], ["red", "blue"]])
def test_rgb_component_subsets_do_not_require_unselected_components(names):
    data = payload()
    data["application"]["channels"]["names"] = names
    HueSaturationRequest.model_validate(data)
    SCHEMA.validate(data)


def test_adjustment_mode_is_explicit():
    data = payload()
    del data["adjustment"]["mode"]
    assert_rejected(data)


def test_palette_all_entries_and_selected_cels_remain_available():
    data = payload(3)
    data["application"]["entries"] = {"kind": "all"}
    HueSaturationRequest.model_validate(data)
    SCHEMA.validate(data)
    data = payload(4)
    data["application"]["cels_target"] = {
        "kind": "selected",
        "layers": [{"layer_path": [1, 2]}],
        "frame_numbers": [1, 2],
    }
    HueSaturationRequest.model_validate(data)
    SCHEMA.validate(data)
