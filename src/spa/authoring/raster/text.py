"""Evidence for assessed native text paths; no callable text Descriptor."""

from spa.contracts.public import CapabilityGap


def text_capability_gap(version: str) -> CapabilityGap:
    return CapabilityGap(
        capability="native text rasterization",
        aseprite_version=version,
        evidence=(
            "No callable text Descriptor. On the macOS Aseprite 1.3.18.5-dev "
            "baseline (API 41), headless PasteText with fresh preferences crashed "
            "before applying explicit font arguments. With an explicit font "
            "preference, PasteText completed but produced zero text pixels; "
            "Image.context:fillText also produced zero pixels and measureText "
            "returned 0x0. Both non-crashing paths stayed blank after save/reopen. "
            "These observations are not retested during discovery of the selected "
            "runtime; they do not establish Linux behavior or permanent native "
            "impossibility. See issue #47 and docs/evidence/issue-47-native-text.md."
        ),
    )
