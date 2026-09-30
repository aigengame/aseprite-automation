"""Tag requests keep addressing and stored values explicit."""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from spa.authoring.document.tag import (
    TagAddRequest,
    TagAddress,
    TagGetRequest,
    TagSetProperties,
    get_tag,
)
from spa.contracts.ports import KernelInvocationResult, RuntimeIssue
from spa.contracts.public import Diagnostics
from tests.support import operation_services


@pytest.mark.parametrize(
    "address",
    [{}, {"tag_index": 1, "tag_name": "walk"}, {"tag_index": 0}],
)
def test_tag_address_requires_one_valid_current_selector(address: dict) -> None:
    with pytest.raises(ValidationError):
        TagAddress.model_validate(address)


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"repeats": None},
        {"repeats": -1},
        {"repeats": 65536},
        {"direction": "sideways"},
    ],
)
def test_tag_set_requires_nonempty_native_patch(patch: dict) -> None:
    with pytest.raises(ValidationError):
        TagSetProperties.model_validate(patch)


def test_tag_add_requires_ordered_inclusive_range() -> None:
    payload = {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "name": "walk",
        "from_frame": 3,
        "to_frame": 2,
        "direction": "forward",
        "repeats": 0,
    }
    with pytest.raises(ValidationError):
        TagAddRequest.model_validate(payload)


def test_empty_tag_name_is_a_valid_present_name() -> None:
    assert TagAddress(tag_name="").tag_name == ""
    assert TagSetProperties(name="").name == ""


@pytest.mark.parametrize("name", ["foo\x00bar", "\x00"])
def test_nul_name_is_rejected_before_native_truncation(name: str) -> None:
    with pytest.raises(ValidationError):
        TagAddress(tag_name=name)
    with pytest.raises(ValidationError):
        TagSetProperties(name=name)
    with pytest.raises(ValidationError):
        TagAddRequest(
            source_sprite_file="source.aseprite",
            target_sprite_file="target.aseprite",
            in_place=False,
            overwrite=False,
            name=name,
            from_frame=1,
            to_frame=1,
            direction="forward",
            repeats=0,
        )


@pytest.mark.parametrize("address", [{"tag_index": 2}, {"tag_name": "second"}])
def test_get_rejects_handler_selection_that_disagrees_with_address(
    address: dict,
) -> None:
    metadata = {
        "width": 1,
        "height": 1,
        "color_mode": "rgb",
        "frame_count": 1,
        "tag_count": 2,
        "palette_count": 0,
        "layer_count": 0,
        "cel_count": 0,
        "slice_count": 0,
        "tileset_count": 0,
        "transparent_color_index": 0,
        "grid_bounds": {"x": 0, "y": 0, "width": 1, "height": 1},
        "pixel_ratio": {"width": 1, "height": 1},
        "use_layer_uuids": False,
    }
    tags = [
        {
            "name": name,
            "from_frame": 1,
            "to_frame": 1,
            "direction": "forward",
            "repeats": 0,
            "color": {"red": 0, "green": 0, "blue": 0, "alpha": 255},
        }
        for name in ("first", "second")
    ]
    response = KernelInvocationResult(
        payload={
            "sprite": {
                "metadata": metadata,
                "frames": None,
                "tags": tags,
                "palettes": None,
                "layers": None,
                "cels": None,
                "slices": None,
                "tilesets": None,
            },
            "selected_index": 1,
        },
        response_path="/response.json",
        diagnostics=Diagnostics(exit_status=0),
    )
    services = replace(
        operation_services(lambda _request: None),
        invoke_kernel=lambda *_args: response,
    )
    request = TagGetRequest.model_validate(
        {"sprite_file": "source.aseprite", "target": address}
    )
    with pytest.raises(RuntimeIssue, match="invalid Tag facts") as rejected:
        get_tag(request, services)
    assert rejected.value.kind == "response_malformed"
