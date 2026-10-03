"""Create and independently observe persisted empty Tilemap Cels through SPA."""

from pathlib import Path

import pytest

from tests.tile.support import fixture, run

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("plan", [False, True], ids=["standalone", "plan"])
@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("frame_number", [1, 3])
def test_create_empty_tilemap_cel(
    tmp_path: Path, runtime, plan: bool, mode: str, frame_number: int
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="cel_creation.lua", mode=mode)
    before = source.read_bytes()
    address = {"layer": {"layer_path": [2]}, "frame_number": frame_number}
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


def test_manifest_observes_empty_tilemap_creation(runtime) -> None:
    assert "aseprite_tile_cel_creation" in runtime.verified_capabilities


@pytest.mark.parametrize("plan", [False, True], ids=["standalone", "plan"])
@pytest.mark.parametrize(
    "address, geometry, expected",
    [
        (
            {"layer": {"layer_path": [2]}, "frame_number": 2},
            {"tilemap_size": {"width": 2, "height": 3}},
            "cel_already_exists",
        ),
        (
            {"layer": {"layer_path": [2]}, "frame_number": 4},
            {"tilemap_size": {"width": 2, "height": 3}},
            "cel_frame_out_of_bounds",
        ),
        (
            {"layer": {"layer_path": [9]}, "frame_number": 1},
            {"tilemap_size": {"width": 2, "height": 3}},
            "layer_invalid_path",
        ),
        (
            {"layer": {"layer_path": [2]}, "frame_number": 1},
            {},
            "cel_unsupported_target",
        ),
        (
            {"layer": {"layer_path": [2]}, "frame_number": 1},
            {"image_size": {"width": 2, "height": 3}},
            "cel_unsupported_target",
        ),
        (
            {"layer": {"layer_path": [1]}, "frame_number": 3},
            {"tilemap_size": {"width": 2, "height": 3}},
            "cel_unsupported_target",
        ),
    ],
)
def test_creation_refusal_preserves_files(
    tmp_path: Path, runtime, plan: bool, address: dict, geometry: dict, expected: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="cel_creation.lua")
    before = source.read_bytes()
    target.write_bytes(b"preserve prior Target")
    files = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
    }
    inputs = {"target": address, **geometry}
    code, result = (
        run(
            "plan",
            "run",
            plan=files | {"steps": [{"operation": "cel add", "input": inputs}]},
        )
        if plan
        else run("cel", "add", **files, **inputs)
    )
    assert code == 2, result
    assert result["code"] == expected, result
    if plan:
        assert result["details"]["step_number"] == 1
    assert source.read_bytes() == before
    assert target.read_bytes() == b"preserve prior Target"
    assert set(tmp_path.iterdir()) == {source, target}


def test_plan_creates_independent_cels_at_first_and_later_frame(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="cel_creation.lua", mode="indexed")
    steps = [
        {
            "operation": "cel add",
            "input": {
                "target": {"layer": {"layer_name": "map"}, "frame_number": number},
                "tilemap_size": {"width": 2, "height": 3},
            },
        }
        for number in (1, 3)
    ]
    code, result = run(
        "plan",
        "run",
        plan={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "steps": steps,
        },
    )
    assert code == 0, result
    assert all(step["result"]["cel"]["linked_cels"] == [] for step in result["steps"])
    fixture(source, runtime, script="cel_creation.lua", result=target, added_count=2)


def test_failed_later_step_does_not_publish_added_tilemap(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="cel_creation.lua")
    before = source.read_bytes()
    target.write_bytes(b"unchanged Target")
    step = {
        "operation": "cel add",
        "input": {
            "target": {"layer": {"layer_path": [2]}, "frame_number": 1},
            "tilemap_size": {"width": 2, "height": 3},
        },
    }
    code, result = run(
        "plan",
        "run",
        plan={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            "steps": [step, step],
        },
    )
    assert code == 2 and result["code"] == "cel_already_exists", result
    assert result["details"]["step_number"] == 2
    assert source.read_bytes() == before
    assert target.read_bytes() == b"unchanged Target"
    assert set(tmp_path.iterdir()) == {source, target}


def test_later_step_can_link_the_new_cel_without_rechecking_initial_independence(
    tmp_path: Path, runtime
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    fixture(source, runtime, script="cel_creation.lua")
    code, result = run(
        "plan",
        "run",
        plan={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "steps": [
                {
                    "operation": "cel add",
                    "input": {
                        "target": {"layer": {"layer_path": [2]}, "frame_number": 1},
                        "tilemap_size": {"width": 2, "height": 3},
                    },
                },
                {
                    "operation": "frame duplicate",
                    "input": {"source_frame_number": 1, "cel_mode": "link"},
                },
            ],
        },
    )
    assert code == 0, result
    assert result["steps"][0]["result"]["cel"]["linked_cels"] == []
    assert result["persisted_reopen_verified"] is True
    code, observed = run(
        "cel",
        "get",
        sprite_file=str(target),
        target={"layer": {"layer_path": [2]}, "frame_number": 1},
    )
    assert code == 0, observed
    assert observed["cel"]["linked_cels"] == [{"layer_path": [2], "frame_number": 2}]
