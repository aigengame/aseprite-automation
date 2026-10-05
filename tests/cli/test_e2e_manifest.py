"""Installed manifest tests against a real Aseprite executable."""

import json
import os
import sys

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
    conversion_available = (
        "aseprite_convert_color_profile" in manifest["runtime"]["verified_capabilities"]
    )
    assert conversion_available or sys.platform == "linux"
    expected_operations = [
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
    }
    if not conversion_available:
        expected_eligible.remove("spa sprite convert-color-profile")
    assert {
        name for name, eligible in eligibility.items() if eligible
    } == expected_eligible
    for entry in manifest["operations"]:
        command = entry["operation"].split()[1:]
        assert entry == json.loads(spa(*command, "--schema").stdout)
        Draft202012Validator.check_schema(entry["request_schema"])
        Draft202012Validator.check_schema(entry["result_schema"])
        Draft202012Validator.check_schema(entry["failure_schema"])
        Draft202012Validator.check_schema(entry["invocation_schema"])
