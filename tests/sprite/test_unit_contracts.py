"""Published contracts owned by the Sprite Domain Module."""

import pytest
from pydantic import ValidationError

from spa.sprite import (
    SliceFacts,
    SpriteCreateRequest,
    SpriteExpectedFacts,
    SpriteGetRequest,
    TagFacts,
)


def test_create_requires_explicit_target_dimensions_mode_and_layer_choice() -> None:
    with pytest.raises(ValidationError) as missing:
        SpriteCreateRequest.model_validate({})

    assert {error["loc"] for error in missing.value.errors()} == {
        ("target_sprite_file",),
        ("width",),
        ("height",),
        ("color_mode",),
        ("initial_layer",),
        ("overwrite",),
    }


@pytest.mark.parametrize("field", ["source_sprite_file", "in_place"])
def test_create_rejects_source_and_in_place_mutation_fields(field: str) -> None:
    request = {
        "target_sprite_file": "created.aseprite",
        "width": 3,
        "height": 2,
        "color_mode": "rgb",
        "initial_layer": {"kind": "transparent"},
        "overwrite": False,
        field: True,
    }

    with pytest.raises(ValidationError) as invalid:
        SpriteCreateRequest.model_validate(request)

    assert invalid.value.errors()[0]["loc"] == (field,)


def test_get_normalizes_requested_sections_and_identifies_unrequested_sections() -> (
    None
):
    request = SpriteGetRequest.model_validate(
        {
            "sprite_file": "created.aseprite",
            "inspection_scope": ["layers", "frames"],
        }
    )

    assert request.inspection_scope == ["frames", "layers"]
    assert request.unrequested_sections == [
        "tags",
        "palettes",
        "cels",
        "slices",
        "tilesets",
    ]


def test_sprite_files_have_the_native_extension() -> None:
    with pytest.raises(ValidationError):
        SpriteGetRequest.model_validate(
            {"sprite_file": "created.png", "inspection_scope": []}
        )


def test_validation_requires_at_least_one_expected_sprite_fact() -> None:
    with pytest.raises(ValidationError):
        SpriteExpectedFacts.model_validate({})


@pytest.mark.parametrize(
    "direction", ["forward", "reverse", "ping_pong", "ping_pong_reverse"]
)
def test_tag_facts_preserve_only_native_animation_directions(direction: str) -> None:
    tag = TagFacts.model_validate(
        {
            "name": "walk",
            "from_frame": 1,
            "to_frame": 2,
            "direction": direction,
            "repeats": 65535,
            "color": {"red": 1, "green": 2, "blue": 3, "alpha": 255},
        }
    )

    assert tag.direction == direction


@pytest.mark.parametrize(
    ("field", "value"), [("direction", "unknown_7"), ("repeats", 65536)]
)
def test_tag_facts_reject_values_outside_the_native_contract(
    field: str, value: object
) -> None:
    payload: dict[str, object] = {
        "name": "walk",
        "from_frame": 1,
        "to_frame": 2,
        "direction": "forward",
        "repeats": 0,
        "color": {"red": 1, "green": 2, "blue": 3, "alpha": 255},
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        TagFacts.model_validate(payload)


def test_slice_facts_require_persisted_user_data() -> None:
    with pytest.raises(ValidationError) as missing:
        SliceFacts.model_validate({"name": "panel", "keys": []})

    assert missing.value.errors()[0]["loc"] == ("data",)
