"""Application-owned Aseprite runtime compatibility checks."""

from dataclasses import replace

from spa.application import dispatch
from spa.contracts import FailureEnvelope
from spa.descriptors import OPERATIONS
from spa.ports import RuntimeObservation


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
            api_version=40,
            lua_version="Lua 5.3",
            verified_capabilities=(
                "aseprite_scripting",
                "lua_file_io",
                "aseprite_json",
            ),
        )

    outcome = dispatch(
        replace(info, execute=execute),
        None,
        {"aseprite": "/aseprite"},
        probe,
    )

    assert isinstance(outcome, FailureEnvelope)
    assert outcome.code == "runtime_incompatible"
    assert len(probes) == 1
    assert executions == []
