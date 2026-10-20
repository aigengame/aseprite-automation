"""Cel existence and lifecycle through the installed CLI and real Aseprite."""

from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, render_frame, run, run_lua
from tests.support import observe_cli, process_diagnostics

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"


def _cels_sprite(runtime: RuntimeObservation, target: Path) -> None:
    """Write the absent, transparent and nonempty Cel Sprite of `cels.lua` to target."""
    lua = run_lua(FIXTURES / "cels.lua", runtime, out=target)
    assert lua.returncode == 0, process_diagnostics(lua)


def test_list_distinguishes_absent_transparent_and_nonempty_cels(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    _cels_sprite(runtime, source)
    listing = expect_success(
        "cel list",
        {
            "sprite_file": str(source),
            "layer": {"layer_path": [1]},
            "from_frame": 1,
            "to_frame": 3,
        },
    )
    assert [cel["content"] for cel in listing["cels"]] == [
        "absent",
        "transparent",
        "nonempty",
    ]
    assert listing["cels"][0]["exists"] is False
    assert listing["cels"][1]["exists"] is True
    assert listing["cels"][1]["position"] == {"x": 1, "y": 0}
    assert listing["cels"][1]["image_bounds"] == {
        "x": 1,
        "y": 0,
        "width": 2,
        "height": 2,
    }


def test_tilemap_cel_existence_does_not_mix_canvas_and_tile_cell_bounds(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "tilemap.aseprite"
    lua = run_lua(FIXTURES / "tilemap.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "cel get",
        {
            "sprite_file": str(source),
            "target": {"layer": {"layer_path": [2]}, "frame_number": 1},
        },
    )
    assert result["cel"]["exists"] is True
    assert result["cel"]["is_tilemap"] is True
    assert result["cel"]["position"] == {"x": 4, "y": 2}
    assert result["cel"]["image_bounds"] is None


def test_add_with_explicit_image_size_survives_reopen(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "added.aseprite"
    _cels_sprite(runtime, source)
    target = {"layer": {"layer_path": [1]}, "frame_number": 1}
    added = expect_success(
        "cel add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target_file),
            "in_place": False,
            "overwrite": False,
            "target": target,
            "image_size": {"width": 5, "height": 5},
        },
    )
    assert added["cel"]["image_bounds"] == {"x": 0, "y": 0, "width": 5, "height": 5}
    assert added["cel"]["content"] == "transparent"
    reopened = expect_success(
        "cel get", {"sprite_file": str(target_file), "target": target}
    )
    assert reopened["cel"] == added["cel"]


def test_add_and_remove_preserve_explicit_cel_existence(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    added_file = tmp_path / "added.aseprite"
    removed_file = tmp_path / "removed.aseprite"
    _cels_sprite(runtime, source)
    target = {"layer": {"layer_path": [1]}, "frame_number": 1}
    absent = expect_success("cel get", {"sprite_file": str(source), "target": target})
    assert absent["cel"]["exists"] is False

    added = expect_success(
        "cel add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(added_file),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    assert added["persisted_reopen_verified"] is True
    assert added["cel"]["content"] == "transparent"
    reopened = expect_success(
        "cel get", {"sprite_file": str(added_file), "target": target}
    )
    assert reopened["cel"] == added["cel"]

    collision = tmp_path / "collision.aseprite"
    outcome = run(
        "cel add",
        {
            "source_sprite_file": str(added_file),
            "target_sprite_file": str(collision),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    failure = outcome.envelope
    assert outcome.returncode == 2, failure
    assert failure["code"] == "cel_already_exists"
    assert not collision.exists()

    removed = expect_success(
        "cel remove",
        {
            "source_sprite_file": str(added_file),
            "target_sprite_file": str(removed_file),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    assert removed["cel"]["exists"] is False
    reopened = expect_success(
        "cel get", {"sprite_file": str(removed_file), "target": target}
    )
    assert reopened["cel"] == removed["cel"]

    missing = tmp_path / "missing.aseprite"
    outcome = run(
        "cel remove",
        {
            "source_sprite_file": str(removed_file),
            "target_sprite_file": str(missing),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    failure = outcome.envelope
    assert outcome.returncode == 2, failure
    assert failure["code"] == "cel_not_found"
    assert not missing.exists()


@pytest.mark.parametrize("number", [1, 2, 3])
def test_background_cel_clear_requires_explicit_color_at_each_frame(
    runtime: RuntimeObservation, tmp_path: Path, number: int
) -> None:
    source = tmp_path / "background.aseprite"
    target_file = tmp_path / "cleared.aseprite"
    lua = run_lua(FIXTURES / "background.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    target = {"layer": {"layer_path": [1]}, "frame_number": number}
    common = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target_file),
        "in_place": False,
        "overwrite": False,
        "target": target,
    }
    for operation in ("add", "remove"):
        outcome = run(f"cel {operation}", common)
        failure = outcome.envelope
        assert outcome.returncode == 2, failure
        assert failure["code"] == "cel_unsupported_target"
        assert not target_file.exists()
    outcome = run("cel clear", common)
    failure = outcome.envelope
    assert outcome.returncode == 2, failure
    assert failure["code"] == "cel_background_color_required"
    assert not target_file.exists()

    color = {"kind": "rgba", "red": 3, "green": 7, "blue": 11, "alpha": 255}
    cleared = expect_success("cel clear", {**common, "background_color": color})
    assert cleared["cel"]["exists"] is True
    assert cleared["cel"]["is_background"] is True
    assert cleared["cel"]["image_bounds"] == {
        "x": 0,
        "y": 0,
        "width": 4,
        "height": 3,
    }
    assert cleared["persisted_reopen_verified"] is True
    reopened = expect_success(
        "cel get", {"sprite_file": str(target_file), "target": target}
    )
    assert reopened["cel"] == cleared["cel"]
    rgba = render_frame(target_file, number)
    assert all(
        rgba.getpixel((x, y)) == (3, 7, 11, 255)
        for y in range(rgba.height)
        for x in range(rgba.width)
    )


def test_get_reports_native_linked_cels_after_reopen(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    linked_file = tmp_path / "linked.aseprite"
    _cels_sprite(runtime, source)
    expect_success(
        "frame duplicate",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked_file),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 3,
            "cel_mode": "link",
        },
    )
    for number, other in ((3, 4), (4, 3)):
        result = expect_success(
            "cel get",
            {
                "sprite_file": str(linked_file),
                "target": {"layer": {"layer_path": [1]}, "frame_number": number},
            },
        )
        assert result["cel"]["content"] == "nonempty"
        assert result["cel"]["linked_cels"] == [
            {"layer_path": [1], "frame_number": other}
        ]


def test_clear_reports_and_preserves_all_native_linked_cels(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    linked_file = tmp_path / "linked.aseprite"
    cleared_file = tmp_path / "cleared.aseprite"
    _cels_sprite(runtime, source)
    expect_success(
        "frame duplicate",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(linked_file),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 3,
            "cel_mode": "link",
        },
    )
    target = {"layer": {"layer_path": [1]}, "frame_number": 3}
    result = expect_success(
        "cel clear",
        {
            "source_sprite_file": str(linked_file),
            "target_sprite_file": str(cleared_file),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    assert result["before"]["content"] == "nonempty"
    assert result["persisted_reopen_verified"] is True
    assert [
        (cel["layer_path"], cel["frame_number"], cel["content"])
        for cel in result["affected_cels"]
    ] == [([1], 3, "transparent"), ([1], 4, "transparent")]
    for number, other in ((3, 4), (4, 3)):
        reopened = expect_success(
            "cel get",
            {
                "sprite_file": str(cleared_file),
                "target": {"layer": {"layer_path": [1]}, "frame_number": number},
            },
        )
        assert reopened["cel"]["content"] == "transparent"
        assert reopened["cel"]["linked_cels"] == [
            {"layer_path": [1], "frame_number": other}
        ]


@pytest.mark.parametrize("image_size", [None, {"width": 5, "height": 5}])
def test_plan_adds_cel_then_paints_it_in_one_commit(
    runtime: RuntimeObservation, tmp_path: Path, image_size: dict | None
) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "painted.aseprite"
    _cels_sprite(runtime, source)
    request = {
        "plan": {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target_file),
            "steps": [
                {
                    "operation": "cel add",
                    "input": {
                        "target": {
                            "layer": {"layer_path": [1]},
                            "frame_number": 1,
                        },
                        "image_size": image_size,
                    },
                },
                {
                    "operation": "paint apply",
                    "input": {
                        "target": {"layer_path": [1], "frame_number": 1},
                        "patch": {
                            "coordinate_space": "image-pixel",
                            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                            "runs": [
                                {
                                    "x": 0,
                                    "y": 0,
                                    "length": 1,
                                    "color": {
                                        "kind": "rgba",
                                        "red": 255,
                                        "green": 0,
                                        "blue": 0,
                                        "alpha": 255,
                                    },
                                }
                            ],
                        },
                    },
                },
            ],
        },
    }
    process, result, observations = observe_cli(
        "valid",
        "plan run",
        request,
        tmp_path / "observations.json",
        seam="invoke_direct",
    )
    assert process.returncode == 0, process_diagnostics(process)
    assert observations == {
        "native_invocations": 1,
        "commits": 1,
    }
    assert result["persisted_reopen_verified"] is True
    assert [step["operation"] for step in result["steps"]] == [
        "cel add",
        "paint apply",
    ]
    assert result["steps"][0]["result"]["cel"]["content"] == "transparent"
    assert result["steps"][0]["result"]["cel"]["image_bounds"] == {
        "x": 0,
        "y": 0,
        **(image_size or {"width": 4, "height": 3}),
    }
    reopened = expect_success(
        "cel get",
        {
            "sprite_file": str(target_file),
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        },
    )
    assert reopened["cel"]["content"] == "nonempty"


def test_paint_requires_existing_cel_and_does_not_create_one(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "painted.aseprite"
    _cels_sprite(runtime, source)
    outcome = run(
        "paint apply",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target_file),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1], "frame_number": 1},
            "patch": {
                "coordinate_space": "image-pixel",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                "runs": [],
            },
        },
    )
    assert outcome.returncode == 2, outcome.envelope
    assert outcome.envelope["code"] == "cel_not_found"
    assert not target_file.exists()


def test_clear_preserves_regular_cel_and_image_bounds(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "cleared.aseprite"
    _cels_sprite(runtime, source)
    target = {"layer": {"layer_path": [1]}, "frame_number": 3}
    cleared = expect_success(
        "cel clear",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target_file),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    assert cleared["before"]["content"] == "nonempty"
    assert cleared["cel"]["content"] == "transparent"
    assert cleared["cel"]["exists"] is True
    assert cleared["cel"]["image_bounds"] == cleared["before"]["image_bounds"]
    reopened = expect_success(
        "cel get", {"sprite_file": str(target_file), "target": target}
    )
    assert reopened["cel"] == cleared["cel"]


def test_plan_paint_without_cel_fails_with_typed_outcome(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "painted.aseprite"
    _cels_sprite(runtime, source)
    outcome = run(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target_file),
                "steps": [
                    {
                        "operation": "paint apply",
                        "input": {
                            "target": {"layer_path": [1], "frame_number": 1},
                            "patch": {
                                "coordinate_space": "image-pixel",
                                "rectangle": {
                                    "x": 0,
                                    "y": 0,
                                    "width": 1,
                                    "height": 1,
                                },
                                "runs": [],
                            },
                        },
                    }
                ],
            },
        },
    )
    assert outcome.returncode == 2, outcome.envelope
    assert outcome.envelope["code"] == "cel_not_found"
    assert not target_file.exists()


@pytest.mark.parametrize(
    ("fixture", "target", "expected_code", "details_kind"),
    [
        (
            "cels.lua",
            {"layer": {"layer_path": [1]}, "frame_number": 2},
            "cel_already_exists",
            "cel_target",
        ),
        (
            "unsupported_add.lua",
            {"layer": {"layer_path": [2]}, "frame_number": 1},
            "cel_unsupported_target",
            "cel_target",
        ),
        (
            "unsupported_add.lua",
            {"layer": {"layer_path": [3]}, "frame_number": 1},
            "cel_unsupported_target",
            "cel_target",
        ),
        (
            "tilemap.lua",
            {"layer": {"layer_path": [2]}, "frame_number": 1},
            "cel_unsupported_target",
            "cel_target",
        ),
        (
            "background.lua",
            {"layer": {"layer_path": [1]}, "frame_number": 1},
            "cel_unsupported_target",
            "cel_target",
        ),
        (
            "cels.lua",
            {"layer": {"layer_path": [1]}, "frame_number": 99},
            "cel_frame_out_of_bounds",
            "cel_frame_range",
        ),
        (
            "cels.lua",
            {"layer": {"layer_path": [99]}, "frame_number": 1},
            "layer_invalid_path",
            "layer_target",
        ),
    ],
)
@pytest.mark.parametrize("size", [{}, {"image_size": {"width": 5, "height": 5}}])
def test_plan_cel_add_preserves_standalone_typed_refusal(
    runtime: RuntimeObservation,
    tmp_path: Path,
    fixture: str,
    target: dict[str, object],
    expected_code: str,
    details_kind: str,
    size: dict,
) -> None:
    source = tmp_path / "source.aseprite"
    standalone_target = tmp_path / "standalone.aseprite"
    plan_target = tmp_path / "plan.aseprite"
    lua = run_lua(FIXTURES / fixture, runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    source_bytes = source.read_bytes()
    standalone_target.write_bytes(b"prior standalone Target")
    plan_target.write_bytes(b"prior Plan Target")
    outcome = run(
        "cel add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(standalone_target),
            "in_place": False,
            "overwrite": True,
            "target": target,
            **size,
        },
    )
    standalone = outcome.envelope
    assert outcome.returncode == 2, standalone
    assert standalone["code"] == expected_code
    assert standalone_target.read_bytes() == b"prior standalone Target"
    outcome = run(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(plan_target),
                "overwrite": True,
                "steps": [
                    {"operation": "cel add", "input": {"target": target, **size}}
                ],
            },
        },
    )
    assert outcome.returncode == 2, outcome.envelope
    failure = outcome.envelope
    assert failure["code"] == standalone["code"]
    assert failure["details"]["kind"] == details_kind
    assert failure["details"]["step_number"] == 1
    assert plan_target.read_bytes() == b"prior Plan Target"
    assert source.read_bytes() == source_bytes


def test_sized_add_then_failed_step_does_not_publish(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _cels_sprite(runtime, source)
    before = source.read_bytes()
    target.write_bytes(b"prior Target")
    step = {
        "operation": "cel add",
        "input": {
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "image_size": {"width": 5, "height": 5},
        },
    }
    outcome = run(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": True,
                "steps": [step, step],
            },
        },
    )
    assert outcome.returncode == 2, outcome.envelope
    failure = outcome.envelope
    assert failure["code"] == "cel_already_exists"
    assert failure["details"]["step_number"] == 2
    assert source.read_bytes() == before
    assert target.read_bytes() == b"prior Target"
    assert not list(tmp_path.glob("*.staged.aseprite"))
