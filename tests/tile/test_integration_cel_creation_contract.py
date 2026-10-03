"""Installed creation contracts expose geometry and reject invalid input before I/O."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.support import spa


def test_installed_help_explains_the_two_creation_variants() -> None:
    result = spa("cel", "add", "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    for term in ("image_size", "tilemap_size", "Tile Cells", "mutually exclusive"):
        assert term in result.stdout


def test_installed_cel_and_plan_share_tile_geometry_schema() -> None:
    schemas = []
    for command in [("cel", "add"), ("plan", "run")]:
        result = spa(*command, "--schema")
        assert result.returncode == 0, result.stdout + result.stderr
        schema = json.loads(result.stdout)["request_schema"]
        Draft202012Validator.check_schema(schema)
        schemas.append(schema)
    standalone, plan = schemas
    assert standalone["$defs"]["TilemapSize"] == plan["$defs"]["TilemapSize"]
    assert standalone["$defs"]["TilemapSize"]["x-spa-max-tile-cells"] == 1_048_576
    assert (
        standalone["properties"]["tilemap_size"]
        == plan["$defs"]["CelAddInput"]["properties"]["tilemap_size"]
    )
    cel_input = {
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "image_size": {"width": 1, "height": 1},
        "tilemap_size": {"width": 1, "height": 1},
    }
    files = {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
    }
    for schema, request in [
        (standalone, files | cel_input),
        (
            plan,
            {"plan": files | {"steps": [{"operation": "cel add", "input": cel_input}]}},
        ),
    ]:
        assert not Draft202012Validator(schema).is_valid(request)
    for operation in ("clear", "remove"):
        result = spa("cel", operation, "--schema")
        assert (
            "tilemap_size"
            not in json.loads(result.stdout)["request_schema"]["properties"]
        )


@pytest.mark.parametrize("plan", [False, True])
@pytest.mark.parametrize(
    "geometry",
    [
        {"tilemap_size": {"width": 0, "height": 1}},
        {"tilemap_size": {"width": True, "height": 1}},
        {"tilemap_size": {"width": 1, "height": 65536}},
        {"tilemap_size": {"width": 1025, "height": 1024}},
        {"tilemap_size": {"width": 1}},
        {
            "tilemap_size": {"width": 1, "height": 1},
            "image_size": {"width": 1, "height": 1},
        },
    ],
)
def test_invalid_geometry_preserves_files_before_native_launch(
    tmp_path: Path, plan: bool, geometry: dict
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"Source")
    target.write_bytes(b"Target")
    files = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
    }
    cel_input = {
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        **geometry,
    }
    request = (
        {"plan": files | {"steps": [{"operation": "cel add", "input": cel_input}]}}
        if plan
        else files | cel_input
    )
    request["aseprite"] = "/missing/aseprite"
    result = spa(
        *(("plan", "run") if plan else ("cel", "add")),
        "--input-json",
        json.dumps(request),
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert json.loads(result.stdout)["code"] == "invalid_request"
    assert source.read_bytes() == b"Source"
    assert target.read_bytes() == b"Target"
    assert set(tmp_path.iterdir()) == {source, target}
