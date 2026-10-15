"""Public guidance for text rasterization; no callable text Descriptor."""

from spa.contracts.public import CapabilityGap


def text_capability_gap(version: str) -> CapabilityGap:
    return CapabilityGap(
        capability="native text rasterization",
        aseprite_version=version,
        reason="SPA does not provide text rasterization. Import prepared raster text instead.",
    )
