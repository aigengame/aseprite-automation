"""Published Language models and registered failures for the installed slice."""

import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializeAsAny,
)


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Request(PublicModel):
    pass


class VersionRequest(Request):
    pass


class RuntimeRequest(Request):
    aseprite: str | None = Field(default=None, min_length=1)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


ProbePrerequisite = Literal[
    "aseprite_scripting",
    "lua_file_io",
    "aseprite_json",
]
RuntimeCapability = Literal[
    "aseprite_runtime_introspection",
    "aseprite_sprite_create",
    "aseprite_sprite_inspection",
    "aseprite_sprite_flatten",
    "aseprite_sprite_resize",
    "aseprite_sprite_crop",
    "aseprite_layer_hierarchy",
    "aseprite_layer_mutation",
    "aseprite_layer_merge",
    "aseprite_background_conversion",
    "aseprite_paint_apply",
    "aseprite_paint_composite",
    "aseprite_paint_composite_indexed",
    "aseprite_paint_line",
    "aseprite_paint_rectangle",
    "aseprite_paint_ellipse",
    "aseprite_paint_contour",
    "aseprite_paint_blur",
    "aseprite_paint_pencil",
    "aseprite_paint_eraser",
    "aseprite_paint_fill",
    "aseprite_paint_pencil_regular",
    "aseprite_paint_pencil_pixel_perfect",
    "aseprite_paint_pencil_dots",
    "aseprite_paint_eraser_regular",
    "aseprite_paint_eraser_pixel_perfect",
    "aseprite_paint_eraser_dots",
    "aseprite_frame_authoring",
    "aseprite_frame_editing",
    "aseprite_cel_lifecycle",
    "aseprite_cel_relationships",
    "aseprite_image_resize",
    "aseprite_image_snapshot",
    "aseprite_image_canvas_transform",
    "aseprite_image_flip",
    "aseprite_image_rotate",
    "aseprite_tag_authoring",
    "aseprite_palette_entries",
    "aseprite_palette_resize",
    "aseprite_palette_remap",
    "aseprite_palette_reorder",
    "aseprite_filter_brightness_contrast",
    "aseprite_filter_brightness_contrast_tilemap_manual",
    "aseprite_filter_hue_saturation",
    "aseprite_filter_despeckle",
    "aseprite_filter_despeckle_indexed_without_green",
    "aseprite_palette_files",
    "aseprite_palette_quantization",
    "aseprite_change_color_mode",
    "aseprite_assign_color_profile",
    "aseprite_convert_color_profile",
    "aseprite_export_image",
    "aseprite_selection",
]


class RuntimeRequirements(PublicModel):
    lua_language: str = Field(min_length=1)
    minimum_api_version: int = Field(ge=1)
    required_capabilities: list[RuntimeCapability]


class RuntimeFacts(PublicModel):
    selection_source: Literal["explicit", "environment", "path"]
    requested_path: str | None
    discovered_path: str
    canonical_path: str
    resource_complete: bool
    resource_path: str
    aseprite_version: str
    api_version: int
    lua_version: str
    verified_prerequisites: list[ProbePrerequisite]
    verified_capabilities: list[RuntimeCapability]


class CapabilityGap(PublicModel):
    capability: str
    aseprite_version: str
    evidence: str


class VersionResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa version"] = "spa version"
    spa_version: str


class InfoResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa info"] = "spa info"
    spa_version: str
    runtime: RuntimeFacts
    supported_capabilities: list[str]
    capability_gaps: list[CapabilityGap]


class OperationSchema(PublicModel):
    operation: str
    execution_kind: Literal["read", "mutation", "export"]
    determinism: Literal["deterministic"]
    side_effects: list[str]
    minimum_aseprite_version: str | None
    requires_runtime: bool
    plan_eligible: bool = False
    runtime_requirements: RuntimeRequirements | None
    request_schema: dict
    result_schema: dict
    failure_schema: dict
    invocation_schema: dict


class SchemaResult(PublicModel):
    status: Literal["success"] = "success"
    operation: Literal["spa schema"] = "spa schema"
    spa_version: str
    runtime: RuntimeFacts
    operations: list[OperationSchema]
    access_failure_schema: dict
    capability_gaps: list[CapabilityGap]


class NotFoundDetails(PublicModel):
    kind: Literal["executable_not_found"] = "executable_not_found"
    requested_path: str | None
    searched: list[str]


class ResourceDetails(PublicModel):
    kind: Literal["resource_incomplete"] = "resource_incomplete"
    canonical_path: str
    searched: list[str]


class ProcessDetails(PublicModel):
    kind: Literal["process"] = "process"
    executable: str
    exit_status: int | None = None


class ProcessStartDetails(PublicModel):
    kind: Literal["process_start"] = "process_start"
    executable: str
    exit_status: None


class KernelProtocolDetail(PublicModel):
    kind: Literal["kernel_protocol"] = "kernel_protocol"
    response_path: str
    failed_step: int | None = Field(default=None, ge=1)
    failed_operation: str | None = None


class KernelExecutionDetails(PublicModel):
    kind: Literal["kernel_execution"] = "kernel_execution"
    response_path: str
    reason: str
    failed_step: int | None = Field(default=None, ge=1)
    failed_operation: str | None = None


class RuntimeCompatibilityDetails(PublicModel):
    kind: Literal["runtime_compatibility"] = "runtime_compatibility"
    aseprite_version: str
    lua_version: str
    api_version: int
    required_lua_language: str
    minimum_api_version: int
    missing_capabilities: list[RuntimeCapability]


class RequestDetails(PublicModel):
    kind: Literal["invalid_request"] = "invalid_request"
    errors: list["ValidationIssue"]


class ValidationIssue(PublicModel):
    location: list[str | int]
    code: str
    message: str


FailureCategory = Literal["input", "environment", "execution", "kernel_protocol"]


@dataclass(frozen=True)
class FailureCodeSpec:
    code: str
    meaning: str
    category: FailureCategory
    details_type: type[PublicModel]

    @property
    def details_kind(self) -> str:
        return get_args(self.details_type.model_fields["kind"].annotation)[0]


def register_failure_codes(
    specs: tuple[FailureCodeSpec, ...],
) -> Mapping[str, FailureCodeSpec]:
    """Reject invalid registration before it can become a public projection."""
    registered: dict[str, FailureCodeSpec] = {}
    for spec in specs:
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", spec.code):
            raise ValueError(f"Failure Code must be lower_snake_case: {spec.code}")
        if spec.code in registered:
            raise ValueError(f"Duplicate Failure Code: {spec.code}")
        if not spec.meaning.strip():
            raise ValueError(f"Failure Code has no meaning: {spec.code}")
        if spec.category not in get_args(FailureCategory):
            raise ValueError(f"Unknown Failure Category: {spec.category}")
        kind_field = spec.details_type.model_fields.get("kind")
        if (
            not issubclass(spec.details_type, PublicModel)
            or kind_field is None
            or len(get_args(kind_field.annotation)) != 1
        ):
            raise ValueError(f"Unsupported Failure Details type: {spec.details_type}")
        registered[spec.code] = spec
    return MappingProxyType(registered)


CORE_FAILURE_CODE_SPECS = (
    FailureCodeSpec(
        "invalid_request",
        "The public request or CLI invocation is invalid",
        "input",
        RequestDetails,
    ),
    FailureCodeSpec(
        "executable_not_found",
        "The selected Aseprite executable is unavailable",
        "environment",
        NotFoundDetails,
    ),
    FailureCodeSpec(
        "resource_incomplete",
        "Required Aseprite resources are unavailable",
        "environment",
        ResourceDetails,
    ),
    FailureCodeSpec(
        "process_start_failed",
        "Aseprite invocation could not be prepared or started",
        "execution",
        ProcessStartDetails,
    ),
    FailureCodeSpec(
        "process_timeout",
        "The Aseprite process exceeded its deadline",
        "execution",
        ProcessDetails,
    ),
    FailureCodeSpec(
        "output_limit_exceeded",
        "Aseprite process output exceeded the bound",
        "execution",
        ProcessDetails,
    ),
    FailureCodeSpec(
        "process_failed",
        "The Aseprite process failed",
        "execution",
        ProcessDetails,
    ),
    FailureCodeSpec(
        "kernel_response_missing",
        "The private Kernel response is absent",
        "kernel_protocol",
        KernelProtocolDetail,
    ),
    FailureCodeSpec(
        "kernel_response_invalid",
        "The private Kernel response is invalid",
        "kernel_protocol",
        KernelProtocolDetail,
    ),
    FailureCodeSpec(
        "kernel_execution_failed",
        "The packaged Kernel handler refused execution",
        "execution",
        KernelExecutionDetails,
    ),
    FailureCodeSpec(
        "runtime_incompatible",
        "The installed Aseprite Lua language or scripting API version does not meet the Operation requirements",
        "environment",
        RuntimeCompatibilityDetails,
    ),
)


class Diagnostics(PublicModel):
    stdout: str = ""
    stderr: str = ""
    exit_status: int | None = None


class FailureEnvelope(PublicModel):
    status: Literal["failure"] = "failure"
    operation: str
    code: str
    category: FailureCategory
    message: str
    details: SerializeAsAny[PublicModel]
    diagnostics: Diagnostics = Field(default_factory=Diagnostics)


def _registered_spec(
    code: str,
    details: PublicModel,
    failure_codes: Mapping[str, FailureCodeSpec],
) -> FailureCodeSpec:
    spec = failure_codes.get(code)
    if spec is None:
        raise ValueError(f"Unknown Failure Code: {code}")
    if not isinstance(details, spec.details_type):
        raise ValueError(  # noqa: TRY004 - invalid public code/Details pairing
            f"Failure Details for {code} must be {spec.details_kind}"
        )
    return spec


def failure_envelope(
    operation: str,
    code: str,
    message: str,
    details: PublicModel,
    *,
    applicable_codes: tuple[str, ...],
    failure_codes: Mapping[str, FailureCodeSpec],
    diagnostics: Diagnostics | None = None,
) -> FailureEnvelope:
    """Construct a registered failure applicable to its public Operation or Access path."""
    spec = _registered_spec(code, details, failure_codes)
    if code not in applicable_codes:
        raise ValueError(f"Failure Code {code} is not applicable to {operation}")
    return FailureEnvelope(
        operation=operation,
        code=code,
        category=spec.category,
        message=message,
        details=details,
        diagnostics=diagnostics or Diagnostics(),
    )


def failure_schema(
    codes: tuple[str, ...],
    operation: str,
    failure_codes: Mapping[str, FailureCodeSpec],
) -> dict[str, Any]:
    """Project one registered code/Category/Details union as Draft 2020-12."""
    if not codes or len(codes) != len(set(codes)):
        raise ValueError("Failure schema needs unique applicable codes")
    unknown = set(codes) - failure_codes.keys()
    if unknown:
        raise ValueError(f"Unknown Failure Code in schema: {sorted(unknown)}")
    base = FailureEnvelope.model_json_schema()
    definitions = base.pop("$defs", {})
    base["required"] = list(dict.fromkeys([*base["required"], "status"]))
    branches = []
    for code in codes:
        spec = failure_codes[code]
        details_schema = spec.details_type.model_json_schema(
            ref_template="#/$defs/{model}"
        )
        definitions.update(details_schema.pop("$defs", {}))
        definitions[spec.details_type.__name__] = details_schema
        branch = deepcopy(base)
        branch["properties"]["operation"] = {"const": operation}
        branch["properties"]["code"] = {"const": code}
        branch["properties"]["category"] = {"const": spec.category}
        branch["properties"]["details"] = {
            "allOf": [
                {"$ref": f"#/$defs/{spec.details_type.__name__}"},
                {
                    "type": "object",
                    "properties": {"kind": {"const": spec.details_kind}},
                    "required": ["kind"],
                },
            ]
        }
        branches.append(branch)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": definitions,
        "oneOf": branches,
    }
