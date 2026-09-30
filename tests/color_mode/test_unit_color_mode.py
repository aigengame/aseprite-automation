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


@pytest.mark.parametrize(
    "defect", ["not_reopened", "missing_image", "changed_noop", "inapplicable_mapping"]
)
def test_unverified_kernel_result_cannot_replace_existing_target(tmp_path, defect):
    from copy import deepcopy
    from dataclasses import replace
    from pathlib import Path

    from spa.adapters.files import LocalTargetFiles
    from spa.authoring.color.color_mode import change_color_mode
    from spa.contracts.ports import KernelInvocationResult, RuntimeIssue
    from spa.contracts.public import Diagnostics
    from tests.support import operation_services, runtime_observation

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"original source")
    target.write_bytes(b"original target")
    document = {
        "color_mode": "rgb",
        "transparent_color_index": 0,
        "palettes": {
            "frame_count": 1,
            "palette_changes": [
                {
                    "palette_frame_number": 1,
                    "effective_frame_range": {"from_frame": 1, "to_frame": 1},
                    "entries": [
                        {
                            "index": 0,
                            "color": {"red": 0, "green": 0, "blue": 0, "alpha": 0},
                        }
                    ],
                }
            ],
        },
        "images": [
            {
                "image_number": 1,
                "kind": "cel",
                "width": 1,
                "height": 1,
                "bytes_per_pixel": 4,
                "row_stride": 4,
                "content": "0000000000000000",
                "conversion_frame_number": 1,
                "palette_frame_number": 1,
                "palette_indices": None,
            }
        ],
        "cels": [
            {
                "layer_path": [1],
                "frame_number": 1,
                "image_number": 1,
                "opacity": 255,
                "is_background": False,
            }
        ],
        "tilesets": [],
    }
    evidence = {
        "source_color_mode": "rgb",
        "target_color_mode": "rgb",
        "changed": False,
        "to_gray": None,
        "mapping": None,
        "dithering": None,
        "before": document,
        "after": deepcopy(document),
        "persisted_reopen_verified": True,
    }
    if defect == "not_reopened":
        evidence["persisted_reopen_verified"] = False
    elif defect == "missing_image":
        evidence["after"]["images"] = []
    elif defect == "changed_noop":
        evidence["after"]["images"][0]["content"] = "1111111111111111"
    else:
        evidence["mapping"] = {
            "requested_rgb_map_algorithm": "default",
            "effective_rgb_map_algorithm": "octree",
            "color_best_fit_criteria": "default",
        }

    def invoke(_runtime, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"unverified output")
        return KernelInvocationResult(
            payload=evidence,
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    services = replace(
        operation_services(lambda _: runtime_observation("aseprite_change_color_mode")),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
    )
    request = ColorModeRequest.model_validate(
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            "conversion": {"source_color_mode": "rgb", "target": {"color_mode": "rgb"}},
        }
    )
    with pytest.raises(RuntimeIssue, match="Invalid persisted Color Mode evidence"):
        change_color_mode(request, services)
    assert source.read_bytes() == b"original source"
    assert target.read_bytes() == b"original target"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "source.aseprite",
        "target.aseprite",
    ]


@pytest.mark.parametrize("algorithm", ["ordered", "old"])
def test_matrix_omission_and_explicit_null_are_distinct_in_request_and_schema(
    algorithm,
):
    from jsonschema import Draft202012Validator

    valid = request("rgb", {**INDEXED, "dithering": {"algorithm": algorithm}})
    wire = valid.model_dump(exclude_none=True)
    validator = Draft202012Validator(ColorModeRequest.model_json_schema())
    assert validator.is_valid(wire)
    wire["conversion"]["target"]["dithering"]["matrix"] = None
    with pytest.raises(ValidationError, match="Matrix cannot be null"):
        ColorModeRequest.model_validate(wire)
    assert not validator.is_valid(wire)
