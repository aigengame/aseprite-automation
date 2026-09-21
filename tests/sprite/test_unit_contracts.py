"""Published contracts owned by the Sprite Domain Module."""

import pytest
from pydantic import ValidationError

from spa.sprite import SpriteCreateRequest, SpriteGetRequest


def test_create_requires_explicit_target_dimensions_mode_and_layer_choice() -> None:
    with pytest.raises(ValidationError) as missing:
        SpriteCreateRequest.model_validate({})

    assert {error["loc"] for error in missing.value.errors()} == {
        ("target_sprite_file",),
        ("width",),
        ("height",),
        ("color_mode",),
        ("initial_layer",),
    }


@pytest.mark.parametrize("field", ["source_sprite_file", "in_place"])
def test_create_rejects_source_and_in_place_mutation_fields(field: str) -> None:
    request = {
        "target_sprite_file": "created.aseprite",
        "width": 3,
        "height": 2,
        "color_mode": "rgb",
        "initial_layer": {"kind": "transparent"},
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
