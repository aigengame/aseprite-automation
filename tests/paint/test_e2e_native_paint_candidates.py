"""Direct Aseprite observations behind the unpublished Paint candidates."""

import json
import os

import pytest

from spa import SPA_BASELINE_ASEPRITE_VESION
from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.paint.support import FIXTURES
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e


def test_baseline_native_paint_candidate_boundaries(
    runtime: RuntimeObservation,
) -> None:
    if runtime.aseprite_version.partition("-")[0] != SPA_BASELINE_ASEPRITE_VESION:
        pytest.skip("Native candidate checks use Baseline Aseprite")
    lua = run_lua(FIXTURES / "native_paint_candidate_probe.lua", runtime)
    assert lua.returncode == 0, process_diagnostics(lua)
    records = json.loads(
        next(
            line.removeprefix("SPA29_PROBE=")
            for line in lua.stdout.splitlines()
            if line.startswith("SPA29_PROBE=")
        )
    )
    assert all(record["returned_nil"] for record in records.values())

    narrow, wide, slow, no_effect = (
        records["spray_narrow"],
        records["spray_wide"],
        records["spray_slow"],
        records["spray_no_effect"],
    )
    assert (narrow["width"], narrow["speed"]) == (2, 100)
    assert (wide["width"], wide["speed"]) == (16, 100)
    assert (slow["width"], slow["speed"]) == (16, 1)
    assert all(item["preferences_restored"] for item in (narrow, wide, slow, no_effect))
    assert wide["changed"] > narrow["changed"] * 5
    assert wide["changed"] > slow["changed"] * 5
    assert no_effect["changed"] == 0

    assert records["curve_a"]["changed"] == records["curve_b"]["changed"] == 0
    assert records["polygon_a"]["changed"] == records["polygon_b"]["changed"] == 0
    assert records["jumble_a"]["changed"] > 0
    assert records["jumble_b"]["changed"] > 0
    assert records["jumble_a"]["fingerprint"] != records["jumble_b"]["fingerprint"]

    info = spa("info", "--aseprite", os.environ["SPA_TEST_ASEPRITE"])
    manifest = spa("schema", "--aseprite", os.environ["SPA_TEST_ASEPRITE"])
    assert info.returncode == manifest.returncode == 0
    info_result, schema_result = json.loads(info.stdout), json.loads(manifest.stdout)
    candidates = {
        f"spa paint {tool}" for tool in ("spray", "curve", "polygon", "jumble")
    }
    gaps = {
        gap["capability"]: gap
        for gap in info_result["capability_gaps"]
        if gap["capability"] in candidates
    }
    assert set(gaps) == candidates
    assert all(
        gap["aseprite_version"] == runtime.aseprite_version for gap in gaps.values()
    )
    for tool in ("spray", "curve", "polygon", "jumble"):
        assert "SPA does not provide" in gaps[f"spa paint {tool}"]["reason"]
    assert all(gap in schema_result["capability_gaps"] for gap in gaps.values())
    assert candidates.isdisjoint(info_result["supported_capabilities"])
    assert candidates.isdisjoint(
        item["operation"] for item in schema_result["operations"]
    )
