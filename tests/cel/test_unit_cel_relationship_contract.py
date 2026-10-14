"""Relationship operations depend on their own observed runtime behavior."""

from spa.application.surface import _surface
from tests.support import runtime_observation


def test_relationship_surface_does_not_require_cel_lifecycle() -> None:
    runtime = runtime_observation("aseprite_cel_relationships")

    supported, _ = _surface(runtime)

    assert {"spa cel set", "spa cel copy", "spa cel link", "spa cel unlink"} <= set(
        supported
    )
    assert "spa cel add" not in supported
