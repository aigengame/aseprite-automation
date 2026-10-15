"""Text guidance describes SPA availability and preserves selected runtime identity."""

from dataclasses import replace

import pytest

from spa import SPA_BASELINE_ASEPRITE_VESION
from spa.application.surface import info_result, schema_result
from spa.contracts.public import RuntimeRequest
from tests.support import operation_services, runtime_observation


@pytest.mark.parametrize(
    "selected_version", [SPA_BASELINE_ASEPRITE_VESION, "test-runtime"]
)
def test_text_gap_reports_availability_without_research_narrative(
    selected_version: str,
) -> None:
    observation = replace(
        runtime_observation("aseprite_runtime_introspection", "aseprite_paint_line"),
        aseprite_version=selected_version,
    )
    services = operation_services(lambda _: observation)
    info = info_result(RuntimeRequest(), services)
    schema = schema_result(RuntimeRequest(), services)
    gap = next(
        gap
        for gap in info.capability_gaps
        if gap.capability == "native text rasterization"
    )
    assert gap in schema.capability_gaps
    assert gap.aseprite_version == selected_version
    assert "SPA does not provide text rasterization" in gap.reason
    assert "Import prepared raster text" in gap.reason
    assert "spa paint line" in info.supported_capabilities
    assert not any("text" in item.operation.split() for item in schema.operations)
