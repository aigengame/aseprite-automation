"""Installed discovery retains Channel evidence without granting convolution."""

import os

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.application.surface import PROBE_RESOURCES, info_result, schema_result
from spa.contracts.public import RuntimeRequest
from tests.support import operation_services

pytestmark = pytest.mark.e2e


def test_installed_convolution_reports_sources_defaults_and_native_evidence():
    request = RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"])
    observation = probe(request, PROBE_RESOURCES)
    facts = observation.convolution
    assert facts is not None and facts.complete, facts
    assert facts.source_paths and facts.notes
    brightness = [
        resource for resource in facts.resources if resource.name == "brightness"
    ]
    assert brightness and all(
        resource.source_path in facts.source_paths for resource in brightness
    )
    assert all(
        resource.declared_default_channels == ["red", "green", "blue", "gray"]
        for resource in brightness
    )
    probes = facts.probes
    assert len(probes) == 3
    assert [p.requested_channel for p in probes] == ["red", "alpha", "red"]
    assert all(
        p.command_completed and p.before_rgba == [10, 20, 30, 40] for p in probes
    )
    assert all(p.after_rgba == p.reopened_rgba for p in probes)
    # Evidence identity 1.3.18.5: both flags ignored, unknown resource silently no-op.
    assert probes[0].after_rgba == probes[1].after_rgba == [18, 28, 38, 48]
    assert probes[2].after_rgba == probes[2].before_rgba
    services = operation_services(lambda _: observation)
    info = info_result(request, services)
    schema = schema_result(request, services)
    assert info.runtime.convolution == schema.runtime.convolution == facts
    assert "spa filter convolution-matrix" not in info.supported_capabilities
    assert not any(
        operation.operation == "spa filter convolution-matrix"
        for operation in schema.operations
    )
    gap = next(
        gap
        for gap in info.capability_gaps
        if gap.capability == "spa filter convolution-matrix"
    )
    assert gap.aseprite_version == observation.aseprite_version
    assert "changed unrequested components" in gap.evidence
