"""Installed discovery reports the assessed text gap without false callability."""

import json
import os

import pytest

from spa.contracts.public import InfoResult, SchemaResult
from tests.support import spa

pytestmark = pytest.mark.e2e


def test_native_text_gap_is_visible_without_a_callable_operation() -> None:
    executable = os.environ.get("SPA_TEST_INSTALLED_CLI")
    info_run = spa(
        "info", "--aseprite", os.environ["SPA_TEST_ASEPRITE"], executable=executable
    )
    schema_run = spa(
        "schema", "--aseprite", os.environ["SPA_TEST_ASEPRITE"], executable=executable
    )
    assert info_run.returncode == schema_run.returncode == 0
    info = InfoResult.model_validate_json(info_run.stdout)
    schema = SchemaResult.model_validate_json(schema_run.stdout)
    gaps = [
        gap
        for gap in info.capability_gaps
        if gap.capability == "native text rasterization"
    ]
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap in schema.capability_gaps
    assert gap.aseprite_version == info.runtime.aseprite_version
    for fact in ("macOS", "1.3.18.5-dev", "PasteText", "fillText", "save/reopen"):
        assert fact in gap.evidence
    assert "not retested" in gap.evidence
    assert not any("text" in name.split() for name in info.supported_capabilities)
    assert not any("text" in item.operation.split() for item in schema.operations)
    for command in (("text",), ("paint", "text")):
        attempt = spa(*command, "--schema", executable=executable)
        assert attempt.returncode == 2
        assert json.loads(attempt.stdout)["code"] == "invalid_request"
