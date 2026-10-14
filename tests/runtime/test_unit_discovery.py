"""Discovery publishes setup and capability decisions, not raw probe payloads."""

from dataclasses import replace

from spa.application.surface import info_result, schema_result
from spa.contracts.public import ConvolutionDiscovery, ConvolutionProbe, RuntimeRequest
from tests.support import operation_services, runtime_observation


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
        assert "selected runtime changed unrequested components" in gap.evidence
        assert gap.aseprite_version == observation.aseprite_version
        assert any(
            gap.capability == "spa sprite create"
            and "missing observed capabilities" in gap.evidence
            for gap in result.capability_gaps
        )
