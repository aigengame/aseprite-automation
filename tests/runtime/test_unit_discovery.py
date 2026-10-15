"""Discovery publishes setup and capability decisions, not raw probe payloads."""

import re
from dataclasses import replace
from typing import get_args

import pytest

from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import OPERATIONS, info_result, schema_result
from spa.contracts.public import (
    ConvolutionDiscovery,
    ConvolutionProbe,
    RuntimeCapability,
    RuntimeRequest,
)
from tests.support import operation_services, runtime_observation

INTERNAL_REFERENCE = re.compile(
    r"\bBaseline\s+(?:macOS\s+)?Aseprite\b|\bprobe\b|\b(?:issue|PR)\s*#\d+|\bADR-\d+|"
    r"docs/|\bspa\.(?:authoring|application|contracts|adapters|kernel)\b",
    re.IGNORECASE,
)


def assert_caller_guidance(text):
    assert not INTERNAL_REFERENCE.search(text), text


def schema_descriptions(value):
    if isinstance(value, dict):
        if isinstance(value.get("description"), str):
            yield value["description"]
        for key, child in value.items():
            if key not in {"default", "examples", "const", "enum"}:
                yield from schema_descriptions(child)
    elif isinstance(value, list):
        for child in value:
            yield from schema_descriptions(child)


@pytest.mark.parametrize(
    "capabilities", [("aseprite_runtime_introspection",), get_args(RuntimeCapability)]
)
def test_public_guidance_excludes_internal_references(capabilities):
    observation = runtime_observation(*capabilities)
    info = info_result(RuntimeRequest(), operation_services(lambda _: observation))
    for gap in info.capability_gaps:
        assert_caller_guidance(gap.reason)
    for operation in OPERATIONS:
        assert_caller_guidance(operation.help_summary)
        for description in schema_descriptions(
            operation.schema(FAILURE_CODES).model_dump()
        ):
            assert_caller_guidance(description)


def test_guidance_check_detects_an_internal_reference_in_generated_schema():
    from spa.contracts.public import PublicModel

    class InternalDescription(PublicModel):
        """See issue #251 for the internal experiment."""

        value: str

    operation = next(item for item in OPERATIONS if item.name == "version")
    schema = replace(operation, request_type=InternalDescription).schema(FAILURE_CODES)
    with pytest.raises(AssertionError, match="issue #251"):
        for description in schema_descriptions(schema.model_dump()):
            assert_caller_guidance(description)


def test_capability_guidance_uses_reason_in_both_discovery_contracts():
    observation = runtime_observation("aseprite_runtime_introspection")
    services = operation_services(lambda _: observation)
    request = RuntimeRequest()
    info = info_result(request, services)
    manifest = schema_result(request, services)
    assert info.capability_gaps == manifest.capability_gaps
    for result in (info, manifest):
        for gap in result.model_dump()["capability_gaps"]:
            assert set(gap) == {"capability", "aseprite_version", "reason"}
            assert gap["reason"]
            assert gap["aseprite_version"] == observation.aseprite_version


def test_public_runtime_omits_probe_payloads_without_losing_their_gap_decisions():
    observation = replace(
        runtime_observation("aseprite_runtime_introspection"),
        convolution=ConvolutionDiscovery(
            resources=[],
            duplicate_names=[],
            source_paths=["/data/convolution.def"],
            complete=True,
            notes=[],
            probes=[
                ConvolutionProbe(
                    resource_name="brightness",
                    requested_channel="red",
                    command_completed=True,
                    before_rgba=[10, 20, 30, 40],
                    after_rgba=[18, 28, 38, 48],
                    reopened_rgba=[18, 28, 38, 48],
                )
            ],
        ),
    )
    services = operation_services(lambda _: observation)
    request = RuntimeRequest()
    info = info_result(request, services)
    schema = schema_result(request, services)
    assert info.runtime == schema.runtime
    public = info.runtime.model_dump()
    assert not {"requested_path", "discovered_path", "convolution"} & public.keys()
    assert public["canonical_path"] == observation.canonical_path
    assert public["selection_source"] == observation.selection_source
    assert public["resource_complete"] is True
    assert public["verified_capabilities"] == list(observation.verified_capabilities)
    assert public["verified_prerequisites"] == list(observation.verified_prerequisites)
    assert [item.operation for item in schema.operations] == info.supported_capabilities
    for result in (info, schema):
        gap = next(
            gap
            for gap in result.capability_gaps
            if gap.capability == "spa filter convolution-matrix"
        )
        assert "selected runtime changed unrequested components" in gap.reason
        assert gap.aseprite_version == observation.aseprite_version
        assert any(
            gap.capability == "spa sprite create"
            and "missing observed capabilities" in gap.reason
            for gap in result.capability_gaps
        )
