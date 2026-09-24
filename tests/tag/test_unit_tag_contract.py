"""Tag requests keep addressing and stored values explicit."""

import pytest
from pydantic import ValidationError

from spa.tag import TagAddRequest, TagAddress, TagSetProperties


@pytest.mark.parametrize(
    "address",
    [{}, {"tag_index": 1, "tag_name": "walk"}, {"tag_index": 0}, {"tag_name": ""}],
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
