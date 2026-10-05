"""Strict Slice addressing and the bounded installed surface."""

import pytest
from pydantic import ValidationError

from spa.authoring.document.slice import (
    SLICE_MUTATION_REQUIREMENTS,
    SLICE_OPERATIONS,
    SliceAddRequest,
    SliceAddress,
    SliceSetProperties,
)


@pytest.mark.parametrize(
    "address",
    [
        {},
        {"slice_index": 1, "slice_name": "x"},
        {"slice_index": True},
        {"slice_index": 0},
        {"slice_index": "1"},
        {"slice_name": "x\x00y"},
        {"id": "native"},
    ],
)
def test_slice_addresses_reject_inexact_or_nonpublic_forms(address):
    with pytest.raises(ValidationError):
        SliceAddress.model_validate(address)


@pytest.mark.parametrize(
    "properties",
    [
        {},
        {"pivot": None},
        {"bounds": None},
        {"name": None},
        {"data": "x\x00y"},
        {"bounds": {"x": 0, "y": 0, "width": 0, "height": 1}},
        {"center": {"x": 0, "y": 0, "width": 1.5, "height": 1}},
        {"frame_number": 2, "pivot": {"x": 0, "y": 0}},
    ],
)
def test_slice_patch_rejects_unavailable_or_destructive_shapes(properties):
    with pytest.raises(ValidationError):
        SliceSetProperties.model_validate(properties)


def test_center_null_is_an_explicit_clear_and_omission_preserves():
    patch = SliceSetProperties(center=None)
    assert patch.model_dump(exclude_unset=True) == {"center": None}
    assert SliceSetProperties(name="").model_dump(exclude_unset=True) == {"name": ""}


def test_create_has_one_initial_key_and_no_arbitrary_key_api():
    data = {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "name": "slice",
        "bounds": {"x": -1, "y": -2, "width": 1, "height": 2},
    }
    assert SliceAddRequest.model_validate(data).bounds.x == -1
    with pytest.raises(ValidationError):
        SliceAddRequest.model_validate({**data, "frame_number": 2})
    assert {operation.name for operation in SLICE_OPERATIONS} == {
        "slice list",
        "slice get",
        "slice add",
        "slice set",
        "slice remove",
    }
    assert (
        "aseprite_slice_authoring" in SLICE_MUTATION_REQUIREMENTS.required_capabilities
    )
    assert all(not operation.plan_eligible for operation in SLICE_OPERATIONS)
