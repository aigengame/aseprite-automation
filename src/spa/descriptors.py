"""One registration authority for installed Operations."""

from spa.contracts import (
    InfoResult,
    RuntimeFacts,
    RuntimeRequest,
    RuntimeRequirements,
    SchemaResult,
    VersionRequest,
    VersionResult,
    failure_schema,
)
from spa.operation import (
    ACCESS_FAILURE_CODES,
    RUNTIME_FAILURE_CODES,
    OperationDescriptor,
)
from spa.ports import OperationServices
from spa.sprite import SPRITE_OPERATIONS

KERNEL_RUNTIME_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_runtime_introspection"],
)


def version_result(_: VersionRequest, _services: OperationServices) -> VersionResult:
    from importlib.metadata import version

    return VersionResult(spa_version=version("aseprite-automation"))


def info_result(request: RuntimeRequest, services: OperationServices) -> InfoResult:
    from importlib.metadata import version

    observation = services.probe_runtime(request)
    facts = RuntimeFacts(
        selection_source=observation.selection_source,
        requested_path=observation.requested_path,
        discovered_path=observation.discovered_path,
        canonical_path=observation.canonical_path,
        resource_complete=True,
        resource_path=observation.resource_path,
        aseprite_version=observation.aseprite_version,
        api_version=observation.api_version,
        lua_version=observation.lua_version,
        verified_prerequisites=list(observation.verified_prerequisites),
        verified_capabilities=list(observation.verified_capabilities),
    )
    return InfoResult(
        spa_version=version("aseprite-automation"),
        runtime=facts,
        supported_capabilities=[f"spa {descriptor.name}" for descriptor in OPERATIONS],
        capability_gaps=[],
    )


def schema_result(request: RuntimeRequest, services: OperationServices) -> SchemaResult:
    info = info_result(request, services)
    return SchemaResult(
        spa_version=info.spa_version,
        runtime=info.runtime,
        operations=[descriptor.schema() for descriptor in OPERATIONS],
        access_failure_schema=failure_schema(ACCESS_FAILURE_CODES, "spa"),
        capability_gaps=info.capability_gaps,
    )


META_OPERATIONS = (
    OperationDescriptor(
        "info",
        RuntimeRequest,
        InfoResult,
        info_result,
        lambda r: (
            f"Aseprite {r.runtime.aseprite_version} "
            f"(API {r.runtime.api_version}, {r.runtime.lua_version}) "
            f"at {r.runtime.canonical_path}"
        ),
        KERNEL_RUNTIME_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
    OperationDescriptor(
        "version",
        VersionRequest,
        VersionResult,
        version_result,
        lambda r: f"SPA {r.spa_version}",
        None,
        ("invalid_request",),
    ),
    OperationDescriptor(
        "schema",
        RuntimeRequest,
        SchemaResult,
        schema_result,
        lambda r: "\n".join(item.operation for item in r.operations),
        KERNEL_RUNTIME_REQUIREMENTS,
        RUNTIME_FAILURE_CODES,
    ),
)

OPERATIONS = (*META_OPERATIONS, *SPRITE_OPERATIONS)
