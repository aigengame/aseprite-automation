"""Typed observations of the values retained by native Tile.properties reads."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from spa.contracts.public import PublicModel


def selected_namespaces(additional: list[str]) -> list[str]:
    return list(dict.fromkeys(["", "aigengame.spa", *additional]))


class PropertyNil(PublicModel):
    kind: Literal["nil"]


class PropertyBoolean(PublicModel):
    kind: Literal["boolean"]
    value: bool


class PropertyInteger(PublicModel):
    kind: Literal["integer"]
    value: str = Field(pattern=r"^(0|-?[1-9][0-9]*)$")


class PropertyNumber(PublicModel):
    kind: Literal["number"]
    value: float = Field(allow_inf_nan=False)


class PropertyString(PublicModel):
    kind: Literal["string"]
    value: str


class PropertyPoint(PublicModel):
    kind: Literal["point"]
    x: int
    y: int


class PropertySize(PublicModel):
    kind: Literal["size"]
    width: int
    height: int


class PropertyRectangle(PublicModel):
    kind: Literal["rectangle"]
    x: int
    y: int
    width: int
    height: int


class PropertyUuid(PublicModel):
    kind: Literal["uuid"]
    value: str = Field(pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")


class PropertyUnavailable(PublicModel):
    kind: Literal["unavailable"]
    reason: Literal["non_finite_number", "unsupported_native_value"]


type PropertyTableKey = Annotated[
    PropertyString | PropertyInteger, Field(discriminator="kind")
]


class PropertyTableEntry(PublicModel):
    key: PropertyTableKey
    value: PropertyValue


class PropertyTable(PublicModel):
    kind: Literal["table"]
    entries: list[PropertyTableEntry]

    @model_validator(mode="after")
    def unique_keys(self) -> PropertyTable:
        keys = [(entry.key.kind, entry.key.value) for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("Observed table keys must be unique")
        return self


type PropertyValue = Annotated[
    PropertyNil
    | PropertyBoolean
    | PropertyInteger
    | PropertyNumber
    | PropertyString
    | PropertyPoint
    | PropertySize
    | PropertyRectangle
    | PropertyUuid
    | PropertyTable
    | PropertyUnavailable,
    Field(discriminator="kind"),
]


class PropertyEntry(PublicModel):
    name: str
    value: PropertyValue


class PropertyNamespace(PublicModel):
    namespace: str
    entries: list[PropertyEntry]

    @model_validator(mode="after")
    def ordered_names(self) -> PropertyNamespace:
        names = [entry.name for entry in self.entries]
        if names != sorted(set(names)):
            raise ValueError("Property names must be unique and ordered")
        return self
