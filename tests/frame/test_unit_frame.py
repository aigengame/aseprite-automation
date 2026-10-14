"""Frame Operation discovery keeps independent native capabilities separate."""

from dataclasses import replace

from spa.application.surface import _surface
from tests.support import runtime_observation


def test_frame_editing_gap_does_not_hide_existing_add_and_duplicate() -> None:
    runtime = runtime_observation(
        "aseprite_runtime_introspection",
        "aseprite_sprite_inspection",
        "aseprite_frame_authoring",
    )
    supported, gaps = _surface(runtime)

    assert "spa frame add" in supported
    assert "spa frame duplicate" in supported
    for operation in ("set", "move", "remove"):
        name = f"spa frame {operation}"
        assert name not in supported
        assert "aseprite_frame_editing" in next(
            gap.evidence for gap in gaps if gap.capability == name
        )

    without_inspection = replace(
        runtime,
        verified_capabilities=(
            "aseprite_runtime_introspection",
            "aseprite_frame_authoring",
            "aseprite_frame_editing",
        ),
    )
    supported, gaps = _surface(without_inspection)
    for operation in ("add", "duplicate", "set", "move", "remove"):
        name = f"spa frame {operation}"
        assert name not in supported
        assert "aseprite_sprite_inspection" in next(
            gap.evidence for gap in gaps if gap.capability == name
        )
