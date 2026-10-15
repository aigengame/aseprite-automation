"""Convolution discovery has no callable Descriptor in this delivery."""

from spa.contracts.ports import PackagedResource
from spa.contracts.public import CapabilityGap, ConvolutionDiscovery

CONVOLUTION_PROBE_RESOURCE = PackagedResource(
    "convolution_probe", "runtime/convolution_probe.lua"
)


def convolution_capability_gap(
    version: str, discovery: ConvolutionDiscovery | None
) -> CapabilityGap:
    reason = "SPA does not provide Convolution Matrix filtering."
    if discovery:
        for probe in discovery.probes:
            if probe.resource_name != "brightness" or not probe.command_completed:
                continue
            selected = 0 if probe.requested_channel == "red" else 3
            if any(
                before != after
                for index, (before, after) in enumerate(
                    zip(probe.before_rgba, probe.after_rgba, strict=True)
                )
                if index != selected
            ):
                reason += " The selected runtime changed unrequested components."
                break
    return CapabilityGap(
        capability="spa filter convolution-matrix",
        aseprite_version=version,
        reason=reason,
    )
