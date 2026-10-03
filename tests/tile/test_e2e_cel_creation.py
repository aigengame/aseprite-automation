"""Create and independently observe persisted empty Tilemap Cels through SPA."""

from pathlib import Path

import pytest

from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("plan", [False, True], ids=["standalone", "plan"])
def test_create_empty_tilemap_cel(tmp_path: Path, runtime, plan: bool) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="cel_creation.lua")
    before = source.read_bytes()
    address = {"layer": {"layer_path": [2]}, "frame_number": 1}
    files = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
    }
    inputs = {"target": address, "tilemap_size": {"width": 2, "height": 3}}
    code, result = (
        run(
            "plan",
            "run",
            plan=files | {"steps": [{"operation": "cel add", "input": inputs}]},
        )
        if plan
        else run("cel", "add", **files, **inputs)
    )
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    added = result["steps"][0]["result"] if plan else result
    assert added["cel"]["is_tilemap"] is True
    assert added["cel"]["image_bounds"] is None
    assert added["cel"]["content"] == "transparent"
    code, observation = run(
        "tilemap",
        "get",
        sprite_file=str(target),
        target=address,
        rectangle={"x": 0, "y": 0, "width": 2, "height": 3},
    )
    assert code == 0, observation
    assert observation["snapshot"]["entries"] == []
    assert observation["snapshot"]["complete"] is True
    assert observation["tilemap"]["cell_size"] == {"width": 2, "height": 3}
    assert observation["tilemap"]["canvas_coverage"] == {
        "x": 0,
        "y": 0,
        "width": 4,
        "height": 6,
    }
    fixture(source, runtime, script="cel_creation.lua", result=target)
    assert source.read_bytes() == before
