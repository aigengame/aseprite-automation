"""Application-owned Aseprite runtime compatibility checks."""

from dataclasses import replace

import pytest

from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import OPERATIONS
from spa.contracts.ports import RuntimeObservation
from spa.contracts.public import FailureEnvelope
from tests.support import operation_services


def test_incompatible_runtime_is_rejected_before_operation_execution() -> None:
    info = next(descriptor for descriptor in OPERATIONS if descriptor.name == "info")
    executions: list[object] = []
    probes: list[object] = []

    def execute(request: object, _probe: object) -> None:
        executions.append(request)

    def probe(request: object) -> RuntimeObservation:
        probes.append(request)
        return RuntimeObservation(
            selection_source="explicit",
            requested_path="/aseprite",
            discovered_path="/aseprite",
            canonical_path="/aseprite",
            resource_path="/data/gui.xml",
            aseprite_version="old",
            api_version=41,
            lua_version="Lua 5.4",
            verified_prerequisites=(
                "aseprite_scripting",
                "lua_file_io",
                "aseprite_json",
            ),
            verified_capabilities=(),
        )

    outcome = dispatch(
        replace(info, execute=execute),
        None,
        {"aseprite": "/aseprite"},
        operation_services(probe),
        FAILURE_CODES,
    )

    assert isinstance(outcome, FailureEnvelope)
    assert outcome.code == "runtime_incompatible"
    assert outcome.details.missing_capabilities == ["aseprite_runtime_introspection"]
    assert len(probes) == 1
    assert executions == []


@pytest.mark.parametrize(
    ("name", "fields"),
    [
        (
            "tag add",
            {
                "name": "walk",
                "from_frame": 1,
                "to_frame": 1,
                "direction": "forward",
                "repeats": 0,
            },
        ),
        ("tag set", {"target": {"tag_index": 1}, "properties": {"name": "walk"}}),
        ("tag remove", {"target": {"tag_index": 1}}),
    ],
)
def test_tag_mutation_requires_inspection_before_execution(
    name: str, fields: dict
) -> None:
    descriptor = next(item for item in OPERATIONS if item.name == name)
    executions: list[object] = []

    def probe(_request: object) -> RuntimeObservation:
        return RuntimeObservation(
            selection_source="explicit",
            requested_path="/aseprite",
            discovered_path="/aseprite",
            canonical_path="/aseprite",
            resource_path="/data/gui.xml",
            aseprite_version="test",
            api_version=41,
            lua_version="Lua 5.4",
            verified_prerequisites=(
                "aseprite_scripting",
                "lua_file_io",
                "aseprite_json",
            ),
            verified_capabilities=("aseprite_tag_authoring",),
        )

    def execute(request: object, _services: object) -> None:
        executions.append(request)

    outcome = dispatch(
        replace(descriptor, execute=execute),
        None,
        {
            "aseprite": "/aseprite",
            "source_sprite_file": "source.aseprite",
            "target_sprite_file": "target.aseprite",
            "in_place": False,
            "overwrite": False,
            **fields,
        },
        operation_services(probe),
        FAILURE_CODES,
    )

    assert isinstance(outcome, FailureEnvelope)
    assert outcome.code == "runtime_incompatible"
    assert outcome.details.missing_capabilities == ["aseprite_sprite_inspection"]
    assert executions == []
