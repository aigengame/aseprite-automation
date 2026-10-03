"""Shared exact Layer and Cel addresses and Layer target failures."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from spa.contracts.public import FailureCodeSpec, PublicModel

OneBasedIndex = Annotated[int, Field(ge=1)]


class LayerAddress(PublicModel):
    """One exact current path, persisted UUID, or unique Sprite-wide name."""

    layer_path: list[OneBasedIndex] | None = Field(default=None, min_length=1)
    layer_uuid: str | None = Field(default=None, min_length=1)
    layer_name: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def exactly_one(self) -> "LayerAddress":
        if (
            sum(
                value is not None
                for value in (self.layer_path, self.layer_uuid, self.layer_name)
            )
            != 1
        ):
            raise ValueError("Specify exactly one Layer address")
        return self


class LayerTargetDetails(PublicModel):
    kind: Literal["layer_target"] = "layer_target"
    address_role: Literal["target", "parent", "source", "destination"]
    address: LayerAddress
    step_number: int | None = Field(default=None, ge=1)


LAYER_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "layer_missing", "No Layer matches the address", "input", LayerTargetDetails
    ),
    FailureCodeSpec(
        "layer_ambiguous",
        "More than one Layer matches the name",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_invalid_path",
        "The path does not locate a Layer in the current hierarchy",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_uuid_unpersisted",
        "The Sprite does not persist the addressed Layer UUID",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_parent_not_group",
        "The selected parent is not a Group Layer",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_unsupported_target",
        "The selected Layer does not support the requested mutation",
        "input",
        LayerTargetDetails,
    ),
    FailureCodeSpec(
        "layer_invalid_position",
        "The requested position is invalid for the selected Layer's parent",
        "input",
        LayerTargetDetails,
    ),
)
LAYER_TARGET_FAILURE_CODES = tuple(spec.code for spec in LAYER_FAILURE_CODE_SPECS)
LAYER_ADDRESS_FAILURE_CODES = LAYER_TARGET_FAILURE_CODES[:4]


class CelAddress(PublicModel):
    layer: LayerAddress
    frame_number: int = Field(ge=1, strict=True)
