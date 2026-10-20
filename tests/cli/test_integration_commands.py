"""Installed CLI integration tests."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest
from jsonschema import Draft202012Validator, validate
from rich.text import Text

from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import ACCESS_FAILURE_CODES
from spa.contracts.public import RuntimeCapability, failure_schema
from tests.support import (
    cli_entry_command,
    fake_probe_response,
    probe_answer,
    probe_only_aseprite,
    spa,
)


def test_version_is_an_installed_structured_operation() -> None:
    run = spa("version", "--json")
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["operation"] == "spa version"
    assert result["spa_version"]
    version_schema = json.loads(spa("version", "--schema").stdout)
    Draft202012Validator.check_schema(version_schema["result_schema"])
    Draft202012Validator.check_schema(version_schema["invocation_schema"])
    validate(result, version_schema["result_schema"])
    assert (
        "stdin"
        in version_schema["invocation_schema"]["properties"]["input_json"][
            "description"
        ]
    )


def test_runtime_operation_schema_declares_compatibility_requirements() -> None:
    info_schema = json.loads(spa("info", "--schema").stdout)
    assert info_schema["requires_runtime"] is True
    assert info_schema["runtime_requirements"] == {
        "lua_language": "Lua 5.4",
        "minimum_api_version": 41,
        "required_capabilities": ["aseprite_runtime_introspection"],
    }

    version_schema = json.loads(spa("version", "--schema").stdout)
    assert version_schema["requires_runtime"] is False
    assert version_schema["runtime_requirements"] is None


def test_installed_cli_reads_json_request_from_stdin() -> None:
    run = spa("version", "--input-json", "-", stdin="{}")
    assert run.returncode == 0, run.stdout
    assert json.loads(run.stdout)["operation"] == "spa version"

    invalid = spa("version", "--input-json", "-", stdin="{")
    assert invalid.returncode == 2
    assert json.loads(invalid.stdout)["code"] == "invalid_request"


@pytest.fixture(params=["console", "main", "wheel"])
def utf8_cli(request, tmp_path, monkeypatch) -> list[str]:
    return cli_entry_command(request.param, tmp_path, monkeypatch)


@pytest.mark.parametrize(
    "field", ["%SPA_TEST_LITERAL_VALUE%", "$SPA_TEST_LITERAL_VALUE"]
)
def test_installed_cli_preserves_literal_json_fields(
    utf8_cli: list[str], field: str
) -> None:
    request = json.dumps({field: 1})
    environment = os.environ | {"SPA_TEST_LITERAL_VALUE": "expanded-field"}
    failures = []
    for argument in (request, "-"):
        run = subprocess.run(
            [*utf8_cli, "version", "--input-json", argument],
            input=request.encode("utf-8") if argument == "-" else None,
            env=environment,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert run.returncode == 2
        assert run.stderr == b""
        failure = json.loads(run.stdout.decode("utf-8"))
        assert failure["code"] == "invalid_request"
        assert failure["details"]["errors"][0]["location"] == [field]
        assert failure["details"]["errors"][0]["code"] == "extra_forbidden"
        failures.append(failure)
    assert failures[0] == failures[1]
    schema_run = subprocess.run(
        [*utf8_cli, "version", "--schema"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert schema_run.returncode == 0
    assert schema_run.stderr == b""
    schema = json.loads(schema_run.stdout.decode("utf-8"))
    validate(failures[0], schema["failure_schema"])


@pytest.mark.parametrize("field", ["中文", "中文🚀"])
@pytest.mark.parametrize("input_form", ["raw-stdin", "escaped-stdin", "argv"])
def test_installed_cli_preserves_utf8_field_locations(
    utf8_cli: list[str], field: str, input_form: str
) -> None:
    request = json.dumps({field: 1}, ensure_ascii=input_form == "escaped-stdin")
    argument = request if input_form == "argv" else "-"
    run = subprocess.run(
        [*utf8_cli, "version", "--input-json", argument],
        input=request.encode("utf-8") if input_form != "argv" else None,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert run.returncode == 2
    assert run.stderr == b""
    failure = json.loads(run.stdout.decode("utf-8"))
    assert failure["code"] == "invalid_request"
    assert failure["details"]["errors"][0]["location"] == [field]
    assert failure["details"]["errors"][0]["code"] == "extra_forbidden"
    schema_run = subprocess.run(
        [*utf8_cli, "version", "--schema"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert schema_run.returncode == 0
    assert schema_run.stderr == b""
    schema = json.loads(schema_run.stdout.decode("utf-8"))
    validate(failure, schema["failure_schema"])


def test_cli_unicode_usage_failure_is_utf8(utf8_cli: list[str]) -> None:
    run = subprocess.run(
        [*utf8_cli, "不存在🚀"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert run.returncode == 2
    assert run.stderr == b""
    failure = json.loads(run.stdout.decode("utf-8"))
    assert failure["operation"] == "spa"
    assert failure["code"] == "invalid_request"
    error = failure["details"]["errors"][0]
    assert error["code"] == "cli_usage"
    assert "不存在🚀" in error["message"]


@pytest.mark.parametrize("module", ["spa.bootstrap", "spa.mcp_bootstrap"])
def test_importing_process_entry_does_not_reconfigure_stdio(module: str) -> None:
    program = f"""
import sys
before = [(id(stream), stream.encoding, stream.errors)
          for stream in (sys.stdin, sys.stdout, sys.stderr)]
__import__({module!r})
after = [(id(stream), stream.encoding, stream.errors)
         for stream in (sys.stdin, sys.stdout, sys.stderr)]
assert before == after
if {module!r} == 'spa.mcp_bootstrap':
    assert 'spa.access.cli' not in sys.modules
    assert 'spa.application.dispatch' not in sys.modules
"""
    run = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", program],
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert run.returncode == 0, run.stderr


def test_invalid_request_uses_typed_failure_contract() -> None:
    schema = json.loads(spa("version", "--schema").stdout)
    run = spa("version", "--input-json", '{"unexpected": 1}', "--json")
    assert run.returncode == 2
    failure = json.loads(run.stdout)
    validate(failure, schema["failure_schema"])
    assert failure["status"] == "failure"
    assert failure["code"] == "invalid_request"
    assert failure["details"]["kind"] == "invalid_request"
    assert failure["details"]["errors"][0]["location"] == ["unexpected"]


def test_spa_helper_reads_unicode_typed_failure_as_utf8() -> None:
    run = spa("version", "--input-json", json.dumps({"中文🚀": 1}))
    assert run.returncode == 2
    assert run.stderr == ""
    failure = json.loads(run.stdout)
    assert failure["details"]["errors"][0]["location"] == ["中文🚀"]
    assert failure["details"]["errors"][0]["code"] == "extra_forbidden"


def test_invalid_argv_is_on_the_same_failure_channel() -> None:
    run = spa("info", "--timeout-seconds", "not-a-number")
    assert run.returncode == 2
    assert run.stderr == ""
    failure = json.loads(run.stdout)
    assert failure["code"] == "invalid_request"
    assert failure["details"]["errors"][0]["code"] == "cli_usage"


def test_unknown_command_uses_registered_access_failure() -> None:
    run = spa("no-such-operation", "--json")
    assert run.returncode == 2
    assert run.stderr == ""
    failure = json.loads(run.stdout)
    assert failure["operation"] == "spa"
    assert failure["code"] == "invalid_request"
    assert failure["category"] == "input"


@pytest.mark.parametrize("args", [("sprite",), ("sprite", "no-such-operation")])
def test_incomplete_or_unknown_nested_command_uses_access_failure(
    args: tuple[str, ...],
) -> None:
    run = spa(*args)
    assert run.returncode == 2
    assert run.stderr == ""
    failure = json.loads(run.stdout)
    assert failure["operation"] == "spa"
    validate(failure, failure_schema(ACCESS_FAILURE_CODES, "spa", FAILURE_CODES))


def test_bare_invocation_shows_root_help_without_a_runtime(tmp_path) -> None:
    environment = {**os.environ, "SPA_ASEPRITE_EXECUTABLE": str(tmp_path / "missing")}
    run = spa(env=environment)
    assert run.returncode == 0
    assert run.stderr == ""
    help_run = spa("--help", env=environment)
    assert help_run.returncode == 0
    assert "Usage:" in help_run.stdout
    assert run.stdout == help_run.stdout
    assert "spa info --human" in " ".join(Text.from_ansi(run.stdout).plain.split())


def test_human_output_projects_the_same_version_result() -> None:
    version = json.loads(spa("version").stdout)["spa_version"]
    run = spa("version", "--human")
    assert run.returncode == 0
    assert run.stdout.strip() == f"SPA {version}"
    assert (
        json.loads(spa("version", "--human", "--json").stdout)["spa_version"] == version
    )
    assert (
        json.loads(spa("version", "--json", "--human").stdout)["spa_version"] == version
    )


@pytest.mark.parametrize(
    "command_path", [(), ("sprite",), ("sprite", "create"), ("tileset", "tile", "add")]
)
def test_help_navigation_matches_command_help_without_a_runtime(
    command_path, tmp_path
) -> None:
    environment = {**os.environ, "SPA_ASEPRITE_EXECUTABLE": str(tmp_path / "missing")}
    navigated = spa("help", *command_path, env=environment)
    direct = spa(*command_path, "--help", env=environment)
    assert navigated.returncode == direct.returncode == 0
    assert navigated.stderr == direct.stderr == ""
    assert navigated.stdout == direct.stdout
    assert (
        f"Usage: spa{' ' if command_path else ''}{' '.join(command_path)} "
        in Text.from_ansi(direct.stdout).plain
    )


@pytest.mark.parametrize(
    "command_path", [("unknown",), ("sprite", "unknown"), ("sprite", "create", "extra")]
)
def test_help_rejects_unknown_paths_through_access_failure(command_path) -> None:
    run = spa("help", *command_path)
    assert run.returncode == 2
    assert run.stderr == ""
    failure = json.loads(run.stdout)
    validate(failure, failure_schema(ACCESS_FAILURE_CODES, "spa", FAILURE_CODES))
    assert failure["code"] == "invalid_request"


def test_installed_manifest_exposes_access_failures_without_real_aseprite(
    tmp_path: Path,
) -> None:
    binary = fake_probe_response(
        tmp_path, probe_answer(["aseprite_runtime_introspection"])
    )
    run = spa("schema", "--aseprite", str(binary), "--json")
    assert run.returncode == 0, run.stdout
    manifest = json.loads(run.stdout)
    access_schema = manifest["access_failure_schema"]
    Draft202012Validator.check_schema(access_schema)
    validate(json.loads(spa("no-such-operation", "--json").stdout), access_schema)
    assert [item["operation"] for item in manifest["operations"]] == [
        "spa info",
        "spa version",
        "spa schema",
        "spa script run",
        "spa plan check",
    ]
    script = next(
        item for item in manifest["operations"] if item["operation"] == "spa script run"
    )
    assert script["execution_kind"] == "script-run"
    assert script["determinism"] == "caller-defined"
    assert script["plan_eligible"] is False
    assert script["side_effects"] == ["caller-defined"]
    assert all(
        item["determinism"] != "caller-defined"
        for item in manifest["operations"]
        if item is not script
    )
    gaps = {item["capability"]: item["reason"] for item in manifest["capability_gaps"]}
    assert "aseprite_sprite_create" in gaps["spa sprite create"]
    assert "aseprite_sprite_inspection" in gaps["spa sprite get"]
    human = spa(
        "info", "--human", env={**os.environ, "SPA_ASEPRITE_EXECUTABLE": str(binary)}
    )
    assert human.returncode == 0, human.stdout
    assert human.stdout.startswith("Aseprite test (API 41, Lua 5.4)")
    assert f"SPA {manifest['spa_version']}" in human.stdout
    assert f"Executable: {binary.resolve()} (environment)" in human.stdout
    assert "Resources: complete" in human.stdout
    assert "Callable Operations: 5" in human.stdout
    assert "spa schema --human" in human.stdout
    assert "spa sprite create: missing observed capabilities" in human.stdout
    catalog = spa("schema", "--aseprite", str(binary), "--human")
    assert catalog.returncode == 0, catalog.stdout
    assert catalog.stdout.splitlines() == [
        f"{item['operation']}: {item['help_summary']}"
        for item in manifest["operations"]
    ]


@pytest.mark.parametrize(
    "conversion_available", [True, False], ids=["conversion", "no-conversion"]
)
def test_manifest_is_projected_from_command_descriptors(
    tmp_path: Path, conversion_available: bool
) -> None:
    binary = probe_only_aseprite(
        tmp_path,
        [
            capability
            for capability in get_args(RuntimeCapability)
            if conversion_available or capability != "aseprite_convert_color_profile"
        ],
    )
    run = spa("schema", "--aseprite", str(binary))
    assert run.returncode == 0, run.stdout
    manifest = json.loads(run.stdout)
    invalid_argv = json.loads(spa("info", "--timeout-seconds", "nope").stdout)
    validate(invalid_argv, manifest["operations"][0]["failure_schema"])
    expected_operations = [
        "spa info",
        "spa version",
        "spa schema",
        "spa script run",
        "spa sprite create",
        "spa sprite get",
        "spa sprite copy",
        "spa sprite flatten",
        "spa sprite resize",
        "spa sprite crop",
        "spa sprite validate",
        "spa layer list",
        "spa layer get",
        "spa layer add",
        "spa layer set",
        "spa layer move",
        "spa layer remove",
        "spa layer merge",
        "spa layer convert-to-background",
        "spa layer convert-from-background",
        "spa paint apply",
        "spa paint composite",
        "spa paint fill",
        "spa paint eraser",
        "spa paint pencil",
        "spa paint line",
        "spa paint rectangle",
        "spa paint ellipse",
        "spa paint contour",
        "spa paint blur",
        "spa filter brightness-contrast",
        "spa filter color-curve",
        "spa filter replace-color",
        "spa filter hue-saturation",
        "spa filter invert-color",
        "spa filter outline",
        "spa filter despeckle",
        "spa selection create",
        "spa selection combine",
        "spa selection invert",
        "spa selection grow",
        "spa selection shrink",
        "spa selection transform",
        "spa selection validate",
        "spa selection export",
        "spa selection preview",
        "spa frame list",
        "spa frame get",
        "spa frame add",
        "spa frame duplicate",
        "spa frame set",
        "spa frame move",
        "spa frame remove",
        "spa cel list",
        "spa cel get",
        "spa cel add",
        "spa cel clear",
        "spa cel remove",
        "spa cel set",
        "spa cel copy",
        "spa cel link",
        "spa cel unlink",
        "spa motion apply",
        "spa image resize",
        "spa image get",
        "spa image replace",
        "spa image crop",
        "spa image canvas-resize",
        "spa image flip",
        "spa image rotate",
        "spa image import",
        "spa raster prepare",
        "spa tag list",
        "spa tag get",
        "spa tag add",
        "spa tag set",
        "spa tag remove",
        "spa slice list",
        "spa slice get",
        "spa slice add",
        "spa slice set",
        "spa slice remove",
        "spa palette reorder",
        "spa palette remap",
        "spa palette resize",
        "spa palette list",
        "spa palette get",
        "spa palette set",
        "spa palette import",
        "spa palette color-quantization",
        "spa sprite change-color-mode",
        "spa sprite assign-color-profile",
        "spa sprite convert-color-profile",
        "spa export image",
        "spa export gif",
        "spa export sequence",
        "spa export sheet",
        "spa export tileset",
        "spa palette export",
        "spa animation audit",
        "spa animation compare",
        "spa animation preview",
        "spa plan check",
        "spa plan run",
        "spa tileset list",
        "spa tileset get",
        "spa tileset tile get",
        "spa tileset validate",
        "spa tilemap list",
        "spa tilemap get",
        "spa tilemap validate",
        "spa tileset tile add",
        "spa tileset tile assign-key",
        "spa tileset tile remove",
        "spa tileset tile reorder",
        "spa tileset remove",
        "spa layer set-tileset",
        "spa tilemap set",
        "spa tilemap patch",
        "spa tilemap fill",
    ]
    if not conversion_available:
        expected_operations.remove("spa sprite convert-color-profile")
        expected_operations.remove("spa plan run")
    assert [
        entry["operation"] for entry in manifest["operations"]
    ] == expected_operations
    gaps = {gap["capability"]: gap["reason"] for gap in manifest["capability_gaps"]}
    if conversion_available:
        assert "spa sprite convert-color-profile" not in gaps
    else:
        assert (
            "aseprite_convert_color_profile" in gaps["spa sprite convert-color-profile"]
        )
    eligibility = {
        entry["operation"]: entry["plan_eligible"] for entry in manifest["operations"]
    }
    expected_eligible = {
        "spa sprite create",
        "spa sprite get",
        "spa paint apply",
        "spa frame list",
        "spa frame get",
        "spa frame add",
        "spa frame duplicate",
        "spa cel add",
        "spa cel set",
        "spa motion apply",
        "spa sprite change-color-mode",
        "spa sprite assign-color-profile",
        "spa sprite convert-color-profile",
        "spa tileset remove",
        "spa layer set-tileset",
    }
    if not conversion_available:
        expected_eligible.remove("spa sprite convert-color-profile")
    assert {
        name for name, eligible in eligibility.items() if eligible
    } == expected_eligible
