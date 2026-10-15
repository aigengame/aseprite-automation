"""Convolution discovery has no callable Descriptor in this delivery."""

from spa.contracts.ports import PackagedResource
from spa.contracts.public import CapabilityGap

CONVOLUTION_PROBE_RESOURCE = PackagedResource(
    "convolution_probe", "runtime/convolution_probe.lua"
)


def convolution_capability_gap(version: str) -> CapabilityGap:
    return CapabilityGap(
        capability="spa filter convolution-matrix",
        aseprite_version=version,
        reason="SPA does not provide Convolution Matrix filtering.",
    )
