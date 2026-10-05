"""Selected runtime identity does not turn retained text evidence into a new probe."""

from dataclasses import replace

import pytest

from spa.application.surface import info_result, schema_result
from spa.contracts.public import RuntimeRequest
from tests.support import operation_services, runtime_observation


@pytest.mark.parametrize("selected_version", ["1.3.18.5-dev", "1.3.19"])
def test_text_gap_separates_investigation_baseline_from_selected_runtime(
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
    assert "macOS Aseprite 1.3.18.5-dev" in gap.evidence
    assert "not retested" in gap.evidence
    assert "do not establish Linux behavior" in gap.evidence
    assert "spa paint line" in info.supported_capabilities
    assert not any("text" in item.operation.split() for item in schema.operations)
