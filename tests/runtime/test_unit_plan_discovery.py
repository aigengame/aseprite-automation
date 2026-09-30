"""Conservative discovery of the complete eligible Plan Step surface."""

from spa.application.plan import ELIGIBLE_OPERATIONS, PLAN_DISCOVERY_REQUIREMENTS
from spa.application.surface import _surface
from spa.contracts.public import RuntimeFacts


def test_plan_discovery_requires_every_current_eligible_step_capability() -> None:
    expected = {
        capability
        for descriptor in ELIGIBLE_OPERATIONS.values()
        for capability in descriptor.runtime_requirements.required_capabilities
    }
    assert set(PLAN_DISCOVERY_REQUIREMENTS.required_capabilities) == expected

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
        ],
    )
    supported, gaps = _surface(runtime)

    assert "spa sprite get" in supported
    assert "spa plan run" not in supported
    assert next(
        gap for gap in gaps if gap.capability == "spa plan run"
    ).evidence.endswith(
        "aseprite_sprite_create, aseprite_paint_apply, aseprite_frame_authoring, "
        "aseprite_cel_lifecycle, aseprite_cel_relationships, aseprite_change_color_mode"
    )
