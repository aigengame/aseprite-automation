"""Published contracts owned by the Paint Domain Module."""

import pytest
from pydantic import ValidationError

from spa.descriptors import OPERATIONS
from spa.paint import PaintApplyRequest


def _request() -> dict[str, object]:
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "target": {"layer_path": [1], "frame_number": 1},
        "patch": {
            "coordinate_space": "image-pixel",
            "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
            "runs": [
                {
                    "x": 0,
                    "y": 0,
                    "length": 2,
                    "color": {
                        "kind": "rgba",
                        "red": 1,
                        "green": 2,
                        "blue": 3,
                        "alpha": 255,
                    },
                }
            ],
        },
    }


def test_apply_defaults_to_reject_clipping_and_unrestricted_selection() -> None:
    request = PaintApplyRequest.model_validate(_request())

    assert request.clipping == "reject"
    assert request.selection is None
    assert request.patch.coordinate_space == "image-pixel"


def test_apply_is_registered_as_a_mutation() -> None:
    descriptor = next(item for item in OPERATIONS if item.name == "paint apply")

    assert descriptor.request_type is PaintApplyRequest
    assert descriptor.execution_kind == "mutation"
    assert descriptor.failure_codes[-1] == "target_commit_failed"


@pytest.mark.parametrize(
    ("in_place", "target_sprite_file", "overwrite"),
    [
        (True, "other.aseprite", True),
        (True, "source.aseprite", False),
        (False, "source.aseprite", True),
    ],
)
def test_apply_requires_consistent_explicit_target_commit_intent(
    in_place: bool, target_sprite_file: str, overwrite: bool
) -> None:
    payload = _request() | {
        "in_place": in_place,
        "target_sprite_file": target_sprite_file,
        "overwrite": overwrite,
    }

    with pytest.raises(ValidationError):
        PaintApplyRequest.model_validate(payload)


def test_apply_accepts_explicit_in_place_mutation() -> None:
    request = PaintApplyRequest.model_validate(
        _request()
        | {
            "in_place": True,
            "target_sprite_file": "source.aseprite",
            "overwrite": True,
        }
    )

    assert request.in_place is True


@pytest.mark.parametrize("dimension", ["width", "height"])
def test_pixel_patch_rectangle_must_be_positive(dimension: str) -> None:
    payload = _request()
    patch = dict(payload["patch"])  # type: ignore[arg-type]
    rectangle = dict(patch["rectangle"])  # type: ignore[arg-type]
    rectangle[dimension] = 0
    patch["rectangle"] = rectangle
    payload["patch"] = patch

    with pytest.raises(ValidationError):
        PaintApplyRequest.model_validate(payload)


def test_pixel_patch_accepts_an_explicit_empty_run_list() -> None:
    payload = _request()
    patch = dict(payload["patch"])  # type: ignore[arg-type]
    patch["runs"] = []
    payload["patch"] = patch

    assert PaintApplyRequest.model_validate(payload).patch.runs == []


def test_apply_rejects_a_patch_above_its_bounded_tracer_limit() -> None:
    payload = _request()
    patch = dict(payload["patch"])  # type: ignore[arg-type]
    patch["rectangle"] = {"x": 0, "y": 0, "width": 257, "height": 1}
    patch["runs"] = [
        {
            "x": 0,
            "y": 0,
            "length": 257,
            "color": {
                "kind": "rgba",
                "red": 1,
                "green": 2,
                "blue": 3,
                "alpha": 255,
            },
        }
    ]
    payload["patch"] = patch

    with pytest.raises(ValidationError, match="Operation Limit"):
        PaintApplyRequest.model_validate(payload)


@pytest.mark.parametrize(
    "selection",
    [
        {"kind": "empty"},
        {
            "kind": "all",
            "rectangle": {"x": -1, "y": 2, "width": 3, "height": 4},
        },
        {
            "kind": "mask",
            "bounds": {"x": -1, "y": 2, "width": 3, "height": 2},
            "rows": [
                {"y": 2, "runs": [{"x": -1, "length": 1}]},
                {"y": 3, "runs": [{"x": 1, "length": 1}]},
            ],
        },
    ],
)
def test_apply_accepts_canonical_explicit_selection_forms(
    selection: dict[str, object],
) -> None:
    request = PaintApplyRequest.model_validate(_request() | {"selection": selection})

    assert request.selection is not None
    assert request.selection.kind == selection["kind"]


def test_layer_paths_and_frame_numbers_are_one_based() -> None:
    payload = _request()
    payload["target"] = {"layer_path": [0], "frame_number": 0}

    with pytest.raises(ValidationError):
        PaintApplyRequest.model_validate(payload)
