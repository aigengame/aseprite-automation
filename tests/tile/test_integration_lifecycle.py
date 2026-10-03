"""Tile lifecycle public validation must run before native execution."""

import json
import shlex
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.support import fake_aseprite, spa
from tests.tile.support import snapshot


def test_add_schema_exposes_complete_snapshot_and_explicit_mutation() -> None:
    result = spa("tileset", "tile", "add", "--schema")
    assert result.returncode == 0, result.stdout
    schema = json.loads(result.stdout)
    assert schema["execution_kind"] == "mutation"
    assert schema["plan_eligible"] is False
    Draft202012Validator.check_schema(schema["request_schema"])
    Draft202012Validator.check_schema(schema["result_schema"])
    Draft202012Validator.check_schema(schema["failure_schema"])


@pytest.mark.parametrize(
    "defect",
    [
        "no-palette",
        "rgb-palette",
        "origin",
        "coverage",
        "color",
        "empty-key",
        "nul-key",
        "in-place",
    ],
)
def test_invalid_add_does_not_invoke_aseprite(tmp_path: Path, defect: str) -> None:
    marker = tmp_path / "invoked"
    binary = fake_aseprite(tmp_path, f"touch {shlex.quote(str(marker))}\nexit 1")
    image = snapshot()
    request = {
        "aseprite": str(binary),
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "target": {"tileset_index": 1},
        "tile_key": "new",
        "image": image,
    }
    if defect == "no-palette":
        request["image"] = snapshot("indexed")
    elif defect == "rgb-palette":
        request["palette_frame_number"] = 1
    elif defect == "origin":
        image["rectangle"]["x"] = 1
    elif defect == "coverage":
        image["rows"].pop()
    elif defect == "color":
        image["rows"][0][0]["color"] = {"kind": "palette-index", "index": 2}
    elif defect == "empty-key":
        request["tile_key"] = ""
    elif defect == "nul-key":
        request["tile_key"] = "a\0b"
    else:
        request["in_place"] = True
    result = spa("tileset", "tile", "add", "--input-json", json.dumps(request))
    assert result.returncode == 2, result.stdout
    assert json.loads(result.stdout)["code"] == "invalid_request"
    assert not marker.exists()
