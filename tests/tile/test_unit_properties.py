"""Reject lossy or ambiguous public property observations."""

import pytest
from pydantic import TypeAdapter, ValidationError

from spa.authoring.tile.inspection import TilesetGetRequest
from spa.authoring.tile.properties import PropertyNamespace, PropertyValue


@pytest.mark.parametrize(
    "value",
    [
        {"kind": "integer", "value": 9007199254740993},
        {"kind": "integer", "value": "1.5"},
        {"kind": "point", "value": None},
        {"kind": "number", "value": float("inf")},
        {
            "kind": "table",
            "entries": [
                {"key": {"kind": "integer", "value": "1"}, "value": {"kind": "nil"}},
                {"key": {"kind": "integer", "value": "1"}, "value": {"kind": "nil"}},
            ],
        },
    ],
)
def test_observation_cannot_silently_change_value_or_duplicate_keys(
    value: dict,
) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(PropertyValue).validate_python(value)


def test_namespace_cannot_claim_a_scalar_is_a_property_collection() -> None:
    with pytest.raises(ValidationError):
        PropertyNamespace.model_validate(
            {"namespace": "", "value": {"kind": "boolean", "value": True}}
        )


def test_namespace_cannot_be_truncated_at_native_string_boundary() -> None:
    with pytest.raises(ValidationError):
        TilesetGetRequest.model_validate(
            {
                "sprite_file": "source.aseprite",
                "target": {"tileset_index": 1},
                "property_namespaces": ["requested\x00suffix"],
            }
        )
