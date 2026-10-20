"""Cel set bounds must refuse the request before any runtime or file mutation."""

import json
from pathlib import Path

import pytest

from tests.support import spa


@pytest.mark.parametrize(
    ("changes", "location"),
    [
        ({"position": {"x": 32768, "y": 0}}, ["position", "x"]),
        ({"position": {"x": -32769, "y": 0}}, ["position", "x"]),
        ({"position": {"x": 0, "y": 32768}}, ["position", "y"]),
        ({"position": {"x": 0, "y": -32769}}, ["position", "y"]),
        ({"z_index": 32768}, ["z_index"]),
        ({"z_index": -32769}, ["z_index"]),
    ],
)
def test_set_rejects_unpersistable_cel_values(
    tmp_path: Path, changes: dict[str, object], location: list[str]
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    source.write_bytes(b"Source must remain unchanged")
    run = spa(
        "cel",
        "set",
        "--input-json",
        json.dumps(
            {
                "aseprite": "/missing/aseprite",
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": False,
                "overwrite": False,
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                **changes,
            }
        ),
    )
    assert run.returncode == 2, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["code"] == "invalid_request", result
    assert [error["location"] for error in result["details"]["errors"]] == [location]
    assert not target.exists()
    assert source.read_bytes() == b"Source must remain unchanged"
