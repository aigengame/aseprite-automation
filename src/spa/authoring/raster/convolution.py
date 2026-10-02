"""Convolution discovery has no callable Descriptor in this delivery."""

from spa.contracts.ports import PackagedResource
from spa.contracts.public import CapabilityGap, ConvolutionDiscovery

CONVOLUTION_PROBE_RESOURCE = PackagedResource(
    "convolution_probe", "runtime/convolution_probe.lua"
)


def convolution_capability_gap(
    version: str, discovery: ConvolutionDiscovery | None
) -> CapabilityGap:
    evidence = (
        "No callable Descriptor: the complete Convolution acceptance gate has not "
        "passed. Runtime convolution facts report bounded source declarations and "
        "requested versus observed native Channels; resource defaults never grant "
        "Channel support."
    )
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
                evidence += (
                    " The selected runtime changed unrequested components in the "
                    f"{probe.requested_channel} probe."
                )
                break
    return CapabilityGap(
        capability="spa filter convolution-matrix",
        aseprite_version=version,
        evidence=evidence,
    )
