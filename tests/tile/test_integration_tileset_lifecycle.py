"""Tileset contracts reject incomplete intent before native execution."""

import json
import shlex
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.support import fake_aseprite, spa


@pytest.mark.parametrize("command", [("tileset", "remove"), ("layer", "set-tileset")])
def test_lifecycle_schema_exposes_standalone_and_plan_contracts(
    command: tuple[str, ...],
) -> None:
    result = spa(*command, "--schema")
    assert result.returncode == 0, result.stdout
    schema = json.loads(result.stdout)
    assert schema["execution_kind"] == "mutation"
    assert schema["plan_eligible"] is True
    for part in ("request_schema", "result_schema", "failure_schema"):
        Draft202012Validator.check_schema(schema[part])
    assert (
        "aseprite_tileset_lifecycle"
        in schema["runtime_requirements"]["required_capabilities"]
    )


@pytest.mark.parametrize(
    "defect",
    ["grid", "mapping", "duplicate-key", "empty-key", "two-targets", "in-place"],
)
def test_rebind_requires_explicit_valid_intent(tmp_path: Path, defect: str) -> None:
    marker = tmp_path / "invoked"
    binary = fake_aseprite(tmp_path, f"touch {shlex.quote(str(marker))}\nexit 1")
    request = {
        "aseprite": str(binary),
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "layer": {"layer_path": [1]},
        "target": {"tileset_index": 2},
        "grid_policy": "require_equal",
        "mapping": {"kind": "by_key"},
    }
    if defect in {"grid", "mapping"}:
        del request["grid_policy" if defect == "grid" else "mapping"]
    elif defect in {"duplicate-key", "empty-key"}:
        entries = (
            [{"source_key": "a", "target": {"kind": "empty"}}] * 2
            if defect == "duplicate-key"
            else [{"source_key": "", "target": {"kind": "empty"}}]
        )
        request["mapping"] = {"kind": "explicit", "entries": entries}
    elif defect == "two-targets":
        request["target"] = {"tileset_index": 2, "tileset_name": "destination"}
    else:
        request["in_place"] = True
    result = spa("layer", "set-tileset", "--input-json", json.dumps(request))
    assert result.returncode == 2, result.stdout
    assert json.loads(result.stdout)["code"] == "invalid_request"
    assert not marker.exists()
