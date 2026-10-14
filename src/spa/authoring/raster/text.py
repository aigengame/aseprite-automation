"""Evidence for assessed native text paths; no callable text Descriptor."""

from spa.contracts.public import CapabilityGap


def text_capability_gap(version: str) -> CapabilityGap:
    return CapabilityGap(
        capability="native text rasterization",
        aseprite_version=version,
        evidence=(
            "Not callable. Baseline macOS Aseprite 1.3.18.5-dev (API 41): headless "
            "PasteText crashed or produced no pixels; fillText stayed blank after "
            "save/reopen. These observations are not retested during discovery and "
            "do not establish Linux behavior. See docs/evidence/issue-47-native-text.md."
        ),
    )
