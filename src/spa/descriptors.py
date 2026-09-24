"""One registration authority for installed Operations."""

from spa.cel import CEL_OPERATIONS, CEL_SUPPORT_RESOURCE
from spa.contracts import (
    CapabilityGap,
    InfoResult,
    RuntimeFacts,
    RuntimeRequest,
    RuntimeRequirements,
    SchemaResult,
    VersionRequest,
    VersionResult,
    failure_schema,
)
from spa.export import EXPORT_OPERATIONS, EXPORT_PROBE_RESOURCES
from spa.failure_registry import FAILURE_CODES
from spa.frame import FRAME_OPERATIONS, FRAME_SUPPORT_RESOURCE
from spa.layer import LAYER_OPERATIONS, LAYER_SELECT_RESOURCE
from spa.operation import (
    ACCESS_FAILURE_CODES,
    RUNTIME_FAILURE_CODES,
    OperationDescriptor,
)
from spa.paint import PAINT_OPERATIONS, PAINT_PROBE_RESOURCES
from spa.plan import PLAN_OPERATIONS
from spa.ports import OperationServices
from spa.sprite import SPRITE_OPERATIONS, SPRITE_PROBE_RESOURCES
from spa.tag import TAG_OPERATIONS

PROBE_RESOURCES = (
    *SPRITE_PROBE_RESOURCES,
    LAYER_SELECT_RESOURCE,
    *PAINT_PROBE_RESOURCES,
    FRAME_SUPPORT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    *EXPORT_PROBE_RESOURCES,
)

KERNEL_RUNTIME_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_runtime_introspection"],
)


def _runtime_supports(descriptor: OperationDescriptor, runtime: RuntimeFacts) -> bool:
    requirements = descriptor.runtime_requirements
    return requirements is None or (
        runtime.lua_version == requirements.lua_language
        and runtime.api_version >= requirements.minimum_api_version
        and all(
            capability in runtime.verified_capabilities
            for capability in requirements.required_capabilities
        )
    )


def _surface(runtime: RuntimeFacts) -> tuple[list[str], list[CapabilityGap]]:
    supported: list[str] = []
    gaps: list[CapabilityGap] = []
    for descriptor in OPERATIONS:
        command = f"spa {descriptor.name}"
        if _runtime_supports(descriptor, runtime):
            supported.append(command)
            continue
        requirements = descriptor.runtime_requirements
        assert requirements is not None
        missing = [
            capability
            for capability in requirements.required_capabilities
            if capability not in runtime.verified_capabilities
        ]
        evidence = []
        if runtime.lua_version != requirements.lua_language:
            evidence.append(
                f"observed {runtime.lua_version}; requires {requirements.lua_language}"
            )
        if runtime.api_version < requirements.minimum_api_version:
            evidence.append(
                f"observed API {runtime.api_version}; requires API {requirements.minimum_api_version}"
            )
        if missing:
            evidence.append(f"missing observed capabilities: {', '.join(missing)}")
        gaps.append(
            CapabilityGap(
                capability=command,
                aseprite_version=runtime.aseprite_version,
                evidence="; ".join(evidence),
            )
        )
    return supported, gaps


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
    supported, gaps = _surface(facts)
    return InfoResult(
        spa_version=version("aseprite-automation"),
        runtime=facts,
        supported_capabilities=supported,
        capability_gaps=gaps,
    )


def schema_result(request: RuntimeRequest, services: OperationServices) -> SchemaResult:
    info = info_result(request, services)
    return SchemaResult(
        spa_version=info.spa_version,
        runtime=info.runtime,
        operations=[
            descriptor.schema(FAILURE_CODES)
            for descriptor in OPERATIONS
            if f"spa {descriptor.name}" in info.supported_capabilities
        ],
        access_failure_schema=failure_schema(
            ACCESS_FAILURE_CODES, "spa", FAILURE_CODES
        ),
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

OPERATIONS = (
    *META_OPERATIONS,
    *SPRITE_OPERATIONS,
    *LAYER_OPERATIONS,
    *PAINT_OPERATIONS,
    *FRAME_OPERATIONS,
    *CEL_OPERATIONS,
    *TAG_OPERATIONS,
    *EXPORT_OPERATIONS,
    *PLAN_OPERATIONS,
)
