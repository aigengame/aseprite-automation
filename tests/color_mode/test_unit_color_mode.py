"""Conditional request branches reject hidden native choices before execution."""

import pytest
from pydantic import ValidationError

from spa.authoring.color.color_mode import ColorModeRequest


def request(source: str, target: dict) -> ColorModeRequest:
    return ColorModeRequest.model_validate(
        {
            "source_sprite_file": "source.aseprite",
            "target_sprite_file": "target.aseprite",
            "in_place": False,
            "overwrite": False,
            "conversion": {"source_color_mode": source, "target": target},
        }
    )


@pytest.mark.parametrize(
    "source,target",
    [
        ("rgb", {"color_mode": "grayscale"}),
        ("rgb", {"color_mode": "grayscale", "to_gray": "Luma"}),
        ("indexed", {"color_mode": "rgb", "to_gray": "luma"}),
        ("grayscale", {"color_mode": "grayscale", "to_gray": "luma"}),
        ("indexed", {"color_mode": "indexed", "rgb_map_algorithm": "default"}),
        ("rgb", {"color_mode": "rgb", "dithering": {"algorithm": "none"}}),
        ("rgb", {"color_mode": "rgb", "merge_layers": True}),
    ],
)
def test_inapplicable_and_missing_choices(source, target):
    with pytest.raises(ValidationError):
        request(source, target)


INDEXED = {
    "color_mode": "indexed",
    "rgb_map_algorithm": "default",
    "color_best_fit_criteria": "default",
    "dithering": {"algorithm": "none"},
}


@pytest.mark.parametrize(
    "field", ["rgb_map_algorithm", "color_best_fit_criteria", "dithering"]
)
def test_indexed_choices_cannot_be_omitted(field):
    target = dict(INDEXED)
    del target[field]
    with pytest.raises(ValidationError):
        request("rgb", target)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rgb_map_algorithm", "Octree"),
        ("rgb_map_algorithm", "unknown"),
        ("rgb_map_algorithm", 0),
        ("rgb_map_algorithm", None),
        ("color_best_fit_criteria", "linearizedrgb"),
        ("color_best_fit_criteria", 1),
        ("color_best_fit_criteria", "CieLab"),
        ("color_best_fit_criteria", "unknown"),
    ],
)
def test_only_canonical_mapping_names(field, value):
    with pytest.raises(ValidationError):
        request("rgb", {**INDEXED, field: value})


@pytest.mark.parametrize(
    "dithering",
    [
        {"algorithm": "None"},
        {"algorithm": 0},
        {"algorithm": "unknown"},
        {"algorithm": "none", "matrix": {"kind": "installed", "id": "bayer4x4"}},
        {"algorithm": "ordered", "dithering_factor": 1},
        {"algorithm": "old", "dithering_factor": 1},
        {"algorithm": "error-diffusion"},
        {"algorithm": "error-diffusion", "dithering_factor": -0.1},
        {"algorithm": "error-diffusion", "dithering_factor": 1.1},
        {"algorithm": "error-diffusion", "dithering_factor": float("nan")},
        {"algorithm": "error-diffusion", "dithering_factor": float("inf")},
        {
            "algorithm": "error-diffusion",
            "dithering_factor": 1,
            "matrix": {"kind": "file", "path": "matrix.bmp"},
        },
        {
            "algorithm": "ordered",
            "matrix": {"kind": "installed", "id": "bayer4x4", "path": "matrix.bmp"},
        },
    ],
)
def test_dithering_branches_reject_irrelevant_or_invalid_fields(dithering):
    with pytest.raises(ValidationError):
        request("rgb", {**INDEXED, "dithering": dithering})


def test_grayscale_to_indexed_rejects_dithering():
    with pytest.raises(ValidationError):
        request("grayscale", INDEXED)
