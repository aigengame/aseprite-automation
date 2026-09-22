"""Installed CLI tests against a real Aseprite executable."""

import json
import os
import sys
from pathlib import Path

import pytest
from jsonschema import validate

from tests.support import spa

pytestmark = pytest.mark.e2e


def test_info_reports_installed_runtime() -> None:
    run = spa("info", "--aseprite", os.environ["SPA_TEST_ASEPRITE"], "--json")
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["operation"] == "spa info"
    assert result["runtime"]["resource_complete"] is True
    # Pin the evidence profile without using the product version as a runtime gate.
    assert result["runtime"]["aseprite_version"].startswith("1.3.18.5")
    assert result["runtime"]["api_version"] == 41
    assert result["runtime"]["lua_version"] == "Lua 5.4"
    assert result["runtime"]["verified_prerequisites"] == [
        "aseprite_scripting",
        "lua_file_io",
        "aseprite_json",
    ]
    assert result["runtime"]["verified_capabilities"] == [
        "aseprite_runtime_introspection",
        "aseprite_sprite_create",
        "aseprite_sprite_inspection",
        "aseprite_paint_apply",
    ]
    assert result["supported_capabilities"]
    assert result["supported_capabilities"] == [
        "spa info",
        "spa version",
        "spa schema",
        "spa sprite create",
        "spa sprite get",
        "spa paint apply",
    ]
    assert result["capability_gaps"] == []
    info_schema = json.loads(spa("info", "--schema").stdout)
    validate(result, info_schema["result_schema"])
    input_run = spa(
        "info",
        "--input-json",
        json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert input_run.returncode == 0, input_run.stdout
    assert json.loads(input_run.stdout)["runtime"] == result["runtime"]
    human_run = spa("info", "--aseprite", os.environ["SPA_TEST_ASEPRITE"], "--human")
    assert human_run.returncode == 0, human_run.stdout
    assert "Lua 5.4" in human_run.stdout


def test_symlinked_executable_resolves_to_resource_complete_bundle(
    tmp_path: Path,
) -> None:
    link = tmp_path / "aseprite"
    link.symlink_to(os.environ["SPA_TEST_ASEPRITE"])
    run = spa("info", "--aseprite", str(link))
    assert run.returncode == 0, run.stdout
    runtime = json.loads(run.stdout)["runtime"]
    assert runtime["requested_path"] == str(link)
    assert runtime["discovered_path"] == str(link)
    assert runtime["canonical_path"] == str(
        Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    )


@pytest.mark.skipif(
    sys.platform != "darwin"
    or not os.environ.get("SPA_TEST_ASEPRITE")
    or os.environ.get("SPA_TEST_MACOS_AGENT_SANDBOX") != "1",
    reason="requires installed Aseprite in a macOS agent sandbox",
)
def test_macos_agent_sandbox_starts_installed_aseprite_script() -> None:
    executable = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    assert executable.parent.name == "MacOS"
    assert executable.parent.parent.name == "Contents"
    assert executable.parent.parent.parent.suffix == ".app"

    run = spa("info", "--aseprite", str(executable), "--json")
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(result, json.loads(spa("info", "--schema").stdout)["result_schema"])
    assert result["runtime"]["canonical_path"] == str(executable)
    assert result["runtime"]["resource_complete"] is True
