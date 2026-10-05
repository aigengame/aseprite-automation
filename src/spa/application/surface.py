"""One registration authority for installed Operations."""

from spa.application.failure_registry import FAILURE_CODES
from spa.application.plan import PLAN_OPERATIONS
from spa.authoring.color.color_mode import COLOR_MODE_OPERATIONS, COLOR_MODE_RESOURCE
from spa.authoring.color.palette import (
    PALETTE_OPERATIONS,
    PALETTE_PROBE_RESOURCES,
    palette_lifecycle_gaps,
)
from spa.authoring.color.palette_file import PALETTE_FILE_OPERATIONS
from spa.authoring.color.profile import (
    PROFILE_ICC_RESOURCES,
    PROFILE_OPERATIONS,
    PROFILE_RESOURCE,
)
from spa.authoring.color.quantization import (
    PALETTE_QUANTIZATION_RESOURCE,
    QUANTIZATION_OPERATIONS,
)
from spa.authoring.document.animation import ANIMATION_OPERATIONS
from spa.authoring.document.cel import CEL_OPERATIONS
from spa.authoring.document.cel_contracts import CEL_SUPPORT_RESOURCE
from spa.authoring.document.cel_relationship import CEL_RELATIONSHIP_OPERATIONS
from spa.authoring.document.frame import FRAME_OPERATIONS, FRAME_SUPPORT_RESOURCE
from spa.authoring.document.layer import LAYER_OPERATIONS, LAYER_SELECT_RESOURCE
from spa.authoring.document.motion import MOTION_OPERATIONS
from spa.authoring.document.slice import SLICE_OPERATIONS, slice_capability_gaps
from spa.authoring.document.sprite import SPRITE_OPERATIONS, SPRITE_PROBE_RESOURCES
from spa.authoring.document.tag import TAG_OPERATIONS
from spa.authoring.raster.color_curve import (
    COLOR_CURVE_OPERATIONS,
    COLOR_CURVE_RESOURCE,
)
from spa.authoring.raster.convolution import (
    CONVOLUTION_PROBE_RESOURCE,
    convolution_capability_gap,
)
from spa.authoring.raster.despeckle import (
    DESPECKLE_OPERATIONS,
    DESPECKLE_RESOURCE,
    despeckle_capability_gaps,
)
from spa.authoring.raster.filter import (
    FILTER_OPERATIONS,
    FILTER_RESOURCES,
    filter_capability_gaps,
)
from spa.authoring.raster.hue_saturation import (
    HUE_SATURATION_OPERATIONS,
    HUE_SATURATION_RESOURCE,
)
from spa.authoring.raster.image import (
    IMAGE_CANVAS_TRANSFORM_RESOURCE,
    IMAGE_OPERATIONS,
    IMAGE_ORIENTATION_TRANSFORM_RESOURCE,
    IMAGE_RESIZE_TRANSFORM_RESOURCE,
)
from spa.authoring.raster.image_import import IMAGE_IMPORT_OPERATIONS
from spa.authoring.raster.image_snapshot import COMPOSITION_RESOURCE, SNAPSHOT_RESOURCE
from spa.authoring.raster.invert_outline import (
    INVERT_COLOR_RESOURCE,
    INVERT_OUTLINE_OPERATIONS,
    OUTLINE_RESOURCE,
    invert_outline_capability_gaps,
)
from spa.authoring.raster.paint import PAINT_OPERATIONS, PAINT_PROBE_RESOURCES
from spa.authoring.raster.paint_composite import (
    COMPOSITE_OPERATIONS,
    COMPOSITE_SUPPORT_RESOURCE,
    composite_capability_gaps,
)
from spa.authoring.raster.paint_native import (
    NATIVE_PAINT_OPERATIONS,
    NATIVE_PAINT_RESOURCES,
    native_paint_candidate_gaps,
    native_paint_capability_gaps,
)
from spa.authoring.raster.replace_color import (
    REPLACE_COLOR_OPERATIONS,
    REPLACE_COLOR_RESOURCE,
)
from spa.authoring.raster.selection import (
    SELECTION_OPERATIONS,
    SELECTION_SUPPORT_RESOURCE,
)
from spa.authoring.raster.text import text_capability_gap
from spa.authoring.tile.cel_add import tilemap_creation_gaps
from spa.authoring.tile.inspection import TILE_OPERATIONS, TILE_PROBE_RESOURCE
from spa.authoring.tile.layer_creation import TILE_LAYER_PROBE_RESOURCE
from spa.authoring.tile.lifecycle import (
    TILE_LIFECYCLE_OPERATIONS,
    TILE_LIFECYCLE_PROBE_RESOURCE,
)
from spa.authoring.tile.regions import TILE_REGION_OPERATIONS
from spa.authoring.tile.tileset_lifecycle import (
    TILESET_LIFECYCLE_OPERATIONS,
    TILESET_LIFECYCLE_PROBE_RESOURCE,
)
from spa.contracts.operation import (
    ACCESS_FAILURE_CODES,
    RUNTIME_FAILURE_CODES,
    OperationDescriptor,
)
from spa.contracts.ports import OperationServices
from spa.contracts.public import (
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
from spa.delivery.export import EXPORT_OPERATIONS, EXPORT_PROBE_RESOURCES
from spa.delivery.palette import (
    PALETTE_EXPORT_OPERATIONS,
    palette_export_capability_gaps,
)
from spa.delivery.sheet import SHEET_OPERATIONS, SHEET_RESOURCES
from spa.preparation.raster import PREPARATION_OPERATIONS

PROBE_RESOURCES = (
    TILESET_LIFECYCLE_PROBE_RESOURCE,
    TILE_LAYER_PROBE_RESOURCE,
    TILE_PROBE_RESOURCE,
    TILE_LIFECYCLE_PROBE_RESOURCE,
    CONVOLUTION_PROBE_RESOURCE,
    DESPECKLE_RESOURCE,
    *FILTER_RESOURCES,
    COLOR_CURVE_RESOURCE,
    REPLACE_COLOR_RESOURCE,
    HUE_SATURATION_RESOURCE,
    INVERT_COLOR_RESOURCE,
    OUTLINE_RESOURCE,
    PALETTE_QUANTIZATION_RESOURCE,
    COLOR_MODE_RESOURCE,
    *PALETTE_PROBE_RESOURCES,
    PROFILE_RESOURCE,
    *PROFILE_ICC_RESOURCES,
    *NATIVE_PAINT_RESOURCES,
    *SPRITE_PROBE_RESOURCES,
    LAYER_SELECT_RESOURCE,
    *PAINT_PROBE_RESOURCES,
    FRAME_SUPPORT_RESOURCE,
    CEL_SUPPORT_RESOURCE,
    IMAGE_RESIZE_TRANSFORM_RESOURCE,
    SNAPSHOT_RESOURCE,
    COMPOSITION_RESOURCE,
    IMAGE_CANVAS_TRANSFORM_RESOURCE,
    IMAGE_ORIENTATION_TRANSFORM_RESOURCE,
    *EXPORT_PROBE_RESOURCES,
    SELECTION_SUPPORT_RESOURCE,
    COMPOSITE_SUPPORT_RESOURCE,
)

PROBE_RESOURCES = tuple(dict.fromkeys((*PROBE_RESOURCES, *SHEET_RESOURCES)))

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
    if "spa palette export" in supported:
        gaps.extend(
            palette_export_capability_gaps(
                runtime.aseprite_version, runtime.verified_capabilities
            )
        )
    if "spa paint composite" in supported:
        gaps.extend(
            composite_capability_gaps(
                runtime.aseprite_version, runtime.verified_capabilities
            )
        )
    gaps.extend(
        native_paint_capability_gaps(
            runtime.aseprite_version,
            runtime.verified_capabilities,
            contour_available="spa paint contour" in supported,
        )
    )
    registered = {f"spa {descriptor.name}" for descriptor in OPERATIONS}
    gaps.extend(
        gap
        for gap in native_paint_candidate_gaps(runtime.aseprite_version)
        if gap.capability not in registered
    )
    gaps.extend(palette_lifecycle_gaps(runtime.aseprite_version))
    gaps.append(
        convolution_capability_gap(runtime.aseprite_version, runtime.convolution)
    )
    gaps.append(text_capability_gap(runtime.aseprite_version))
    gaps.extend(
        filter_capability_gaps(
            runtime.aseprite_version, runtime.verified_capabilities, supported
        )
    )
    gaps.extend(
        gap
        for gap in invert_outline_capability_gaps(runtime.aseprite_version)
        if gap.capability.split(":")[0] in supported
    )
    if "spa filter despeckle" in supported:
        gaps.extend(despeckle_capability_gaps(runtime.aseprite_version))
    gaps.extend(slice_capability_gaps(runtime.aseprite_version))
    if (
        "spa layer add" in supported
        and "aseprite_tilemap_layer_creation" not in runtime.verified_capabilities
    ):
        gaps.append(
            CapabilityGap(
                capability="spa layer add: tilemap",
                aseprite_version=runtime.aseprite_version,
                evidence="The selected runtime did not verify native Tilemap Layer creation, shared Tileset binding, temporary Tileset removal, and save/reopen persistence.",
            )
        )
    if "spa cel add" in supported:
        gaps.extend(
            tilemap_creation_gaps(
                runtime.aseprite_version, runtime.verified_capabilities
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
        convolution=observation.convolution,
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
    *COMPOSITE_OPERATIONS,
    *NATIVE_PAINT_OPERATIONS,
    *FILTER_OPERATIONS,
    *COLOR_CURVE_OPERATIONS,
    *REPLACE_COLOR_OPERATIONS,
    *HUE_SATURATION_OPERATIONS,
    *INVERT_OUTLINE_OPERATIONS,
    *DESPECKLE_OPERATIONS,
    *SELECTION_OPERATIONS,
    *FRAME_OPERATIONS,
    *CEL_OPERATIONS,
    *CEL_RELATIONSHIP_OPERATIONS,
    *MOTION_OPERATIONS,
    *IMAGE_OPERATIONS,
    *IMAGE_IMPORT_OPERATIONS,
    *PREPARATION_OPERATIONS,
    *TAG_OPERATIONS,
    *SLICE_OPERATIONS,
    *PALETTE_OPERATIONS,
    *PALETTE_FILE_OPERATIONS,
    *QUANTIZATION_OPERATIONS,
    *COLOR_MODE_OPERATIONS,
    *PROFILE_OPERATIONS,
    *EXPORT_OPERATIONS,
    *SHEET_OPERATIONS,
    *PALETTE_EXPORT_OPERATIONS,
    *ANIMATION_OPERATIONS,
    *PLAN_OPERATIONS,
    *TILE_OPERATIONS,
    *TILE_LIFECYCLE_OPERATIONS,
    *TILESET_LIFECYCLE_OPERATIONS,
    *TILE_REGION_OPERATIONS,
)
