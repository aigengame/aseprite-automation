"""Installed manifest tests against a real Aseprite executable."""

import json
import os

import pytest
from jsonschema import Draft202012Validator, validate

from tests.support import spa

pytestmark = pytest.mark.e2e


def test_manifest_is_projected_from_command_descriptors() -> None:
    run = spa("schema", "--aseprite", os.environ["SPA_TEST_ASEPRITE"])
    assert run.returncode == 0, run.stdout
    manifest = json.loads(run.stdout)
    Draft202012Validator.check_schema(manifest["access_failure_schema"])
    unknown = json.loads(spa("no-such-operation", "--json").stdout)
    validate(unknown, manifest["access_failure_schema"])
    invalid_argv = json.loads(spa("info", "--timeout-seconds", "nope").stdout)
    validate(invalid_argv, manifest["operations"][0]["failure_schema"])
    assert [entry["operation"] for entry in manifest["operations"]] == [
        "spa info",
        "spa version",
        "spa schema",
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
        "spa paint eraser",
        "spa paint pencil",
        "spa paint line",
        "spa paint rectangle",
        "spa paint ellipse",
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
        "spa tag list",
        "spa tag get",
        "spa tag add",
        "spa tag set",
        "spa tag remove",
        "spa export image",
        "spa animation audit",
        "spa animation compare",
        "spa animation preview",
        "spa plan check",
        "spa plan run",
    ]
    eligibility = {
        entry["operation"]: entry["plan_eligible"] for entry in manifest["operations"]
    }
    assert {name for name, eligible in eligibility.items() if eligible} == {
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
    }
    for entry in manifest["operations"]:
        command = entry["operation"].split()[1:]
        assert entry == json.loads(spa(*command, "--schema").stdout)
        Draft202012Validator.check_schema(entry["request_schema"])
        Draft202012Validator.check_schema(entry["result_schema"])
        Draft202012Validator.check_schema(entry["failure_schema"])
        Draft202012Validator.check_schema(entry["invocation_schema"])
