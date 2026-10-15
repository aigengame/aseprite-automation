"""Schema annotations for the published Operation contracts."""

from typing import Any

from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema


class CompactJsonSchema(GenerateJsonSchema):
    """Keep authored annotations; omit generated names that repeat schema keys."""

    def field_title_should_be_set(self, schema: Any) -> bool:
        return False

    def model_schema(self, schema: core_schema.ModelSchema) -> JsonSchemaValue:
        result = super().model_schema(schema)
        if result.get("title") == schema["cls"].__name__:
            result.pop("title")
        return result
