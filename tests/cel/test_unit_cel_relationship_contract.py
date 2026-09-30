"""Relationship operations depend on their own observed runtime behavior."""

from spa.application.surface import _surface
from spa.contracts.public import RuntimeFacts


def test_relationship_surface_does_not_require_cel_lifecycle() -> None:
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
        verified_capabilities=["aseprite_cel_relationships"],
    )

    supported, _ = _surface(runtime)

    assert {"spa cel set", "spa cel copy", "spa cel link", "spa cel unlink"} <= set(
        supported
    )
    assert "spa cel add" not in supported
