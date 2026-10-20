"""Tilemap region request contracts reject ambiguous writes before native execution."""

import json
import shlex
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.support import fake_aseprite, spa

PLACEMENT = {
    "kind": "tile",
    "tile_key": "stone",
    "flip_x": False,
    "flip_y": False,
    "flip_diagonal": False,
}
SNAPSHOT = {
    "coordinate_space": "tile-cell",
    "rectangle": {"x": 1, "y": 0, "width": 2, "height": 2},
    "complete": True,
    "default": {"kind": "empty"},
    "entries": [{"tile_x": 1, "tile_y": 0, "placement": PLACEMENT}],
}


@pytest.mark.parametrize("command", ["set", "patch", "fill"])
def test_region_schema_declares_standalone_mutation_and_bounds(command: str) -> None:
    result = spa("tilemap", command, "--schema")
    assert result.returncode == 0, result.stdout
    schema = json.loads(result.stdout)
    assert schema["execution_kind"] == "mutation" and schema["plan_eligible"] is False
    assert schema["request_schema"]["x-spa-operation-limits"] == {
        "tile_cells": 1_048_576,
        "entries": 4096,
    }
    for name in ("request_schema", "result_schema", "failure_schema"):
        Draft202012Validator.check_schema(schema[name])


@pytest.mark.parametrize(
    "defect",
    [
        "duplicate",
        "unsorted",
        "outside",
        "negative-origin",
        "partial",
        "empty-entry",
        "index",
        "null-key",
        "packed",
        "unknown-flag",
        "in-place",
    ],
)
def test_invalid_set_is_rejected_before_runtime(tmp_path: Path, defect: str) -> None:
    marker = tmp_path / "invoked"
    binary = fake_aseprite(tmp_path, f"touch {shlex.quote(str(marker))}\nexit 1")
    snapshot = deepcopy(SNAPSHOT)
    entry = snapshot["entries"][0]
    message = None
    if defect == "duplicate":
        snapshot["entries"].append(deepcopy(entry))
    elif defect == "unsorted":
        snapshot["entries"].insert(
            0, {"tile_x": 2, "tile_y": 1, "placement": deepcopy(PLACEMENT)}
        )
    elif defect == "outside":
        entry["tile_x"] = 3
    elif defect == "negative-origin":
        # The entry stays inside the Rectangle, so only the origin rule refuses it.
        snapshot["rectangle"].update(x=-1, width=3)
        message = "Tile Cell Rectangle origin must be nonnegative"
    elif defect == "partial":
        snapshot["complete"] = False
    elif defect == "empty-entry":
        entry["placement"] = {"kind": "empty"}
    elif defect == "index":
        entry["placement"]["tile_index"] = 1
    elif defect == "null-key":
        entry["placement"]["tile_key"] = None
    elif defect == "packed":
        entry["placement"] = 0x80000001
    elif defect == "unknown-flag":
        entry["placement"]["rotation"] = 90
    request = {
        "aseprite": str(binary),
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": defect == "in-place",
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "snapshot": snapshot,
    }
    result = spa("tilemap", "set", "--input-json", "-", stdin=json.dumps(request))
    failure = json.loads(result.stdout)
    assert result.returncode == 2 and failure["code"] == "invalid_request", (
        result.stdout
    )
    if message is not None:
        assert [error["message"] for error in failure["details"]["errors"]] == [
            f"Value error, {message}"
        ]
    assert not marker.exists()


@pytest.mark.parametrize("count", [4096, 4097])
@pytest.mark.parametrize("command", ["set", "patch"])
def test_region_entries_limit_is_4096(tmp_path: Path, command: str, count: int) -> None:
    marker = tmp_path / "invoked"
    binary = fake_aseprite(tmp_path, f"touch {shlex.quote(str(marker))}\nexit 1")
    # Unique entries in one row, so no other entry rule applies.
    entries = [
        {"tile_x": x, "tile_y": 0, "placement": deepcopy(PLACEMENT)}
        for x in range(count)
    ]
    region = (
        {
            "snapshot": {
                **deepcopy(SNAPSHOT),
                "rectangle": {"x": 0, "y": 0, "width": count, "height": 1},
                "entries": entries,
            }
        }
        if command == "set"
        else {"patch": {"coordinate_space": "tile-cell", "entries": entries}}
    )
    request = {
        "aseprite": str(binary),
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        **region,
    }
    # Send the request on stdin: it is larger than the Linux per-argument limit.
    result = spa("tilemap", command, "--input-json", "-", stdin=json.dumps(request))
    envelope = json.loads(result.stdout)
    if count == 4096:
        # The request passes validation, so the controlled runtime starts.
        assert envelope["code"] != "invalid_request", result.stdout
        assert marker.exists()
        return
    assert result.returncode == 2 and envelope["code"] == "invalid_request"
    [error] = envelope["details"]["errors"]
    assert error["location"] == [next(iter(region)), "entries"]
    assert error["code"] == "too_long"
    assert "at most 4096 items" in error["message"]
    assert not marker.exists()


def test_patch_has_no_duplicate_cells_or_implicit_default(tmp_path: Path) -> None:
    marker = tmp_path / "invoked"
    binary = fake_aseprite(tmp_path, f"touch {shlex.quote(str(marker))}\nexit 1")
    for patch in (
        {"entries": [{"tile_x": 0, "tile_y": 0, "placement": {"kind": "empty"}}] * 2},
        {"entries": [], "default": {"kind": "empty"}},
    ):
        request = {
            "aseprite": str(binary),
            "source_sprite_file": "source.aseprite",
            "target_sprite_file": "target.aseprite",
            "in_place": False,
            "overwrite": False,
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "patch": patch,
        }
        result = spa("tilemap", "patch", "--input-json", json.dumps(request))
        assert (
            result.returncode == 2
            and json.loads(result.stdout)["code"] == "invalid_request"
        ), result.stdout
    assert not marker.exists()
