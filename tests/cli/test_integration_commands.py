"""Installed CLI integration tests."""

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, validate

from spa.contracts import failure_schema
from spa.descriptors import ACCESS_FAILURE_CODES
from tests.support import fake_aseprite, spa


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


def test_installed_cli_reads_json_request_from_stdin() -> None:
    run = spa("version", "--input-json", "-", stdin="{}")
    assert run.returncode == 0, run.stdout
    assert json.loads(run.stdout)["operation"] == "spa version"

    invalid = spa("version", "--input-json", "-", stdin="{")
    assert invalid.returncode == 2
    assert json.loads(invalid.stdout)["code"] == "invalid_request"


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


def test_bare_invocation_emits_only_registered_access_failure() -> None:
    run = spa()
    assert run.returncode == 2
    assert run.stderr == ""
    failure = json.loads(run.stdout)
    validate(failure, failure_schema(ACCESS_FAILURE_CODES, "spa"))
    assert failure["operation"] == "spa"
    assert failure["code"] == "invalid_request"

    help_run = spa("--help")
    assert help_run.returncode == 0
    assert "Usage:" in help_run.stdout


def test_human_output_projects_the_same_version_result() -> None:
    version = json.loads(spa("version").stdout)["spa_version"]
    run = spa("version", "--human")
    assert run.returncode == 0
    assert run.stdout.strip() == f"SPA {version}"
    assert (
        json.loads(spa("version", "--human", "--json").stdout)["spa_version"] == version
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell fixture")
def test_installed_manifest_exposes_access_failures_without_real_aseprite(
    tmp_path: Path,
) -> None:
    binary = fake_aseprite(
        tmp_path,
        """
request=
response=
echo_file=
for argument in "$@"; do
  case "$argument" in
    request=*) request=${argument#request=};;
    response=*) response=${argument#response=};;
    echo=*) echo_file=${argument#echo=};;
  esac
done
cp "$request" "$echo_file"
printf '{"kernel_protocol_version":1,"status":"ok","aseprite_version":"test","api_version":1}' > "$response"
""",
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
    ]
