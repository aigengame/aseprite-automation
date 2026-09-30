"""Direct Aseprite observations behind the unpublished Paint candidates."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import spa

pytestmark = pytest.mark.e2e


def test_aseprite_13185_native_paint_candidate_boundaries(tmp_path: Path) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    if observation.aseprite_version.partition("-")[0] != "1.3.18.5":
        pytest.skip("Issue #29 source and candidate probes target Aseprite 1.3.18.5")
    workspace = tmp_path / "runtime"
    workspace.mkdir()
    prepared = prepare_invocation(
        Path(observation.canonical_path), Path(observation.resource_path), workspace
    )
    fixture = Path(__file__).parent / "fixtures" / "native_paint_candidate_probe.lua"
    run = subprocess.run(
        [str(prepared.executable), "--batch", "--script", str(fixture)],
        env=prepared.environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    records = json.loads(
        next(
            line.removeprefix("SPA29_PROBE=")
            for line in run.stdout.splitlines()
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
        gap["aseprite_version"] == observation.aseprite_version for gap in gaps.values()
    )
    for tool, reason in (
        ("spray", "random draw footprint"),
        ("curve", "Four Points Controller"),
        ("polygon", "Point-by-Point Controller"),
        ("jumble", "zero-velocity Pointers"),
    ):
        assert reason in gaps[f"spa paint {tool}"]["evidence"]
    assert all(gap in schema_result["capability_gaps"] for gap in gaps.values())
    assert candidates.isdisjoint(info_result["supported_capabilities"])
    assert candidates.isdisjoint(
        item["operation"] for item in schema_result["operations"]
    )
