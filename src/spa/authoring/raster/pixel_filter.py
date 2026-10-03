"""Fixed pixel Filter targets, Channels, and observed native Cel writeback."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from spa.authoring.raster.filter import (
    ComponentChannels,
    FilterCelEffect,
    FilterCelsTarget,
    FilterImage,
    FilterMutationRequest,
    FilterTargetObservations,
    validate_cel_effects,
)
from spa.contracts.public import PublicModel
from spa.contracts.raster import (
    ImageContentDigest,
    SelectionApplication,
)

PixelChannel = Literal["red", "green", "blue", "gray", "alpha"]


class IndexChannel(PublicModel):
    kind: Literal["index"]


PixelChannels = Annotated[
    ComponentChannels[PixelChannel] | IndexChannel, Field(discriminator="kind")
]


def pixel_mode_schema() -> dict:
    """Keep mode applicability visible to JSON Schema clients."""
    return {
        "allOf": [
            {
                "if": {"properties": {"color_mode": {"const": mode}}},
                "then": {
                    **(
                        {"required": ["palette_frame_number"]}
                        if mode == "indexed"
                        else {}
                    ),
                    "properties": {
                        "palette_frame_number": {
                            "type": "integer" if mode == "indexed" else "null"
                        },
                        "channels": {
                            "properties": {
                                **(
                                    {"kind": {"const": "components"}}
                                    if mode != "indexed"
                                    else {}
                                ),
                                "names": {"items": {"enum": names}},
                            }
                        },
                    },
                },
            }
            for mode, names in (
                ("rgb", ["red", "green", "blue", "alpha"]),
                ("grayscale", ["gray", "alpha"]),
                ("indexed", ["red", "green", "blue", "alpha"]),
            )
        ]
    }


class PixelFilterRequest(FilterMutationRequest):
    model_config = ConfigDict(json_schema_extra=pixel_mode_schema())
    color_mode: Literal["rgb", "grayscale", "indexed"]
    channels: PixelChannels
    cels_target: FilterCelsTarget
    selection: SelectionApplication | None = None
    palette_frame_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def applicable_channels(self) -> "PixelFilterRequest":
        if (self.color_mode == "indexed") != (self.palette_frame_number is not None):
            raise ValueError(
                "Indexed pixels require a Palette Frame; other modes do not use it"
            )
        if isinstance(self.channels, IndexChannel):
            if self.color_mode != "indexed":
                raise ValueError("Index Channel requires Indexed pixels")
        else:
            allowed = (
                {"gray", "alpha"}
                if self.color_mode == "grayscale"
                else {"red", "green", "blue", "alpha"}
            )
            if not set(self.channels.names) <= allowed:
                raise ValueError("Channels must match Color Mode")
        return self

    def pixel_parameters(self) -> dict:
        return self.model_dump(
            include={
                "color_mode",
                "channels",
                "cels_target",
                "selection",
                "palette_frame_number",
            },
            exclude_none=True,
        )


class PixelFilterEvidence(
    FilterTargetObservations[FilterImage[ImageContentDigest | None], PixelChannels]
):
    cel_effects: list[FilterCelEffect]

    @model_validator(mode="after")
    def consistent_writeback(self) -> "PixelFilterEvidence":
        validate_cel_effects(self, self.cel_effects)
        if self.processed_image_numbers != [
            image.image_number for image in self.images
        ]:
            raise ValueError("Pixel Filter must process every distinct target Image")
        if self.palette_before != self.palette_after:
            raise ValueError("Pixel Filter cannot mutate Palettes")
        return self

    def matches_pixels(self, request: PixelFilterRequest) -> bool:
        channels_match = self.channels == request.channels
        if isinstance(self.channels, ComponentChannels) and isinstance(
            request.channels, ComponentChannels
        ):
            channels_match = set(self.channels.names) == set(request.channels.names)
        return (
            channels_match
            and self.color_mode == request.color_mode
            and self.matches_target_selection(request.cels_target, request.selection)
            and (self.palette_basis.frame_number if self.palette_basis else None)
            == request.palette_frame_number
        )
