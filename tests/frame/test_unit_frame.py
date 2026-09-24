"""Frame Operation discovery keeps independent native capabilities separate."""

from spa.contracts import RuntimeFacts
from spa.descriptors import _surface


def test_frame_editing_gap_does_not_hide_existing_add_and_duplicate() -> None:
    runtime = RuntimeFacts(
        selection_source="explicit",
        requested_path="/aseprite",
        discovered_path="/aseprite",
        canonical_path="/aseprite",
        resource_complete=True,
        resource_path="/resources",
        aseprite_version="test",
        api_version=41,
        lua_version="Lua 5.4",
        verified_prerequisites=["aseprite_scripting", "lua_file_io", "aseprite_json"],
        verified_capabilities=[
            "aseprite_runtime_introspection",
            "aseprite_sprite_inspection",
            "aseprite_frame_authoring",
        ],
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

    without_inspection = runtime.model_copy(
        update={
            "verified_capabilities": [
                "aseprite_runtime_introspection",
                "aseprite_frame_authoring",
                "aseprite_frame_editing",
            ]
        }
    )
    supported, gaps = _surface(without_inspection)
    for operation in ("add", "duplicate", "set", "move", "remove"):
        name = f"spa frame {operation}"
        assert name not in supported
        assert "aseprite_sprite_inspection" in next(
            gap.evidence for gap in gaps if gap.capability == name
        )
