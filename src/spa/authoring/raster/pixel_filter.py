"""Fixed pixel Filter targets, Channels, and observed native Cel writeback."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from spa.authoring.raster.filter import (
    ComponentChannels,
    FilterCel,
    FilterCelsTarget,
    FilterImage,
    FilterMutationRequest,
    FilterTargetObservations,
)
from spa.contracts.public import PublicModel
from spa.contracts.raster import (
    ImageContentDigest,
    PositiveRectangle,
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


class FilterCelEffect(FilterCel):
    image_number: int = Field(ge=1)
    before: PositiveRectangle
    after: PositiveRectangle | None


def validate_cel_effects(observation, effects: list[FilterCelEffect]) -> None:
    """Validate surviving and deleted Cels using stable Layer/Frame identities."""
    if [
        effect.model_dump(include={"layer_path", "frame_number", "image_number"})
        for effect in effects
    ] != [cel.model_dump() for cel in observation.affected_cels]:
        raise ValueError("Cel effects must cover every affected Cel")
    numbers = {image.image_number for image in observation.images}
    if any(effect.image_number not in numbers for effect in effects):
        raise ValueError("Cel effect refers to an unobserved Image")
    for image in observation.images:
        consumers = [
            effect for effect in effects if effect.image_number == image.image_number
        ]
        if not consumers or (image.after_content_digest is not None) != any(
            effect.after is not None for effect in consumers
        ):
            raise ValueError("Image survival disagrees with affected Cels")
    if observation.changed != (
        any(image.changed for image in observation.images)
        or observation.palette_before != observation.palette_after
        or any(effect.before != effect.after for effect in effects)
    ):
        raise ValueError("Filter change disagrees with observed Images and Palettes")


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
            and self.cels_target_kind == request.cels_target.kind
            and self.selection is not None
            and (self.palette_basis.frame_number if self.palette_basis else None)
            == request.palette_frame_number
        )
