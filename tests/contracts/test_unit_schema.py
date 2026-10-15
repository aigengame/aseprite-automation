"""Public schema generation keeps useful constraints without repeated annotations."""

from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator, ValidationError
from pydantic import Field

from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import OPERATIONS
from spa.contracts.public import PublicModel


class SampleItem(PublicModel):
    count: int = Field(default=2, ge=1, le=4, description="Number of copies.")
    label: str = Field(title="Asset label", examples=["hero"])


class SampleRequest(PublicModel):
    item: SampleItem
    payload: dict = Field(default={"title": "literal data", "properties": {"x": 1}})


def test_operation_schema_omits_automatic_titles_but_retains_constraints_and_data():
    descriptor = next(item for item in OPERATIONS if item.name == "version")
    schema = replace(descriptor, request_type=SampleRequest).schema(FAILURE_CODES)
    request = schema.request_schema
    Draft202012Validator.check_schema(request)
    assert "title" not in request
    item = request["$defs"]["SampleItem"]
    assert "title" not in item
    assert item["properties"]["count"] == {
        "type": "integer",
        "default": 2,
        "minimum": 1,
        "maximum": 4,
        "description": "Number of copies.",
    }
    assert item["properties"]["label"]["title"] == "Asset label"
    assert item["properties"]["label"]["examples"] == ["hero"]
    assert request["properties"]["payload"]["default"] == {
        "title": "literal data",
        "properties": {"x": 1},
    }
    validator = Draft202012Validator(request)
    validator.validate({"item": {"label": "hero"}})
    for invalid in ({}, {"item": {"label": "hero", "count": 0}}, {"item": {}}):
        with pytest.raises(ValidationError):
            validator.validate(invalid)


def test_invocation_uses_one_request_contract_and_retains_cli_bindings():
    for descriptor in OPERATIONS:
        schema = descriptor.schema(FAILURE_CODES)
        assert "minimum_aseprite_version" not in schema.model_dump()
        assert "argv" not in schema.invocation_schema["properties"]
        assert schema.invocation_schema["x-cli-flags"] == descriptor.cli_flags
        assert (
            "stdin"
            in schema.invocation_schema["properties"]["input_json"]["description"]
        )
        assert schema.request_schema["type"] == "object"
        assert schema.runtime_requirements == descriptor.runtime_requirements
