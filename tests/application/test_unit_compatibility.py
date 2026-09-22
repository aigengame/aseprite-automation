"""Application-owned Aseprite runtime compatibility checks."""

from dataclasses import replace

from spa.application import dispatch
from spa.contracts import FailureEnvelope
from spa.descriptors import OPERATIONS
from spa.failure_registry import FAILURE_CODES
from spa.ports import RuntimeObservation
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
