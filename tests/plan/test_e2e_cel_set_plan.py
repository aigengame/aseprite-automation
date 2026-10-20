"""Existing Cel property semantics composed in a bounded Operation Plan."""

import json
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts.ports import RuntimeObservation
from tests.image.test_e2e_image_orientation import _fixture as _image_fixture
from tests.image.test_e2e_image_orientation import _inspect
from tests.native_invocation import expect_success, run
from tests.plan.support import FIXTURES, plan_request, red_pixel
from tests.support import cel_relationships_sprite, observe_cli, spa

pytestmark = pytest.mark.e2e


def _cel_set_plan(source: Path, target: Path, inputs: list[dict]) -> dict:
    """Return a `plan run` request with one `cel set` step for each input."""
    return plan_request(
        source, target, [{"operation": "cel set", "input": value} for value in inputs]
    )


def test_cel_set_plan_matches_standalone_and_defers_persistence(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    standalone = tmp_path / "standalone.aseprite"
    planned = tmp_path / "planned.aseprite"
    cel_relationships_sprite(runtime, source)
    changes = {
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "position": {"x": -2, "y": 3},
        "opacity": 0,
        "z_index": -1,
    }
    expected = expect_success(
        "cel set",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(standalone),
            "in_place": False,
            "overwrite": False,
            **changes,
        },
    )

    result = expect_success("plan run", _cel_set_plan(source, planned, [changes]))
    step = result["steps"][0]["result"]
    for field in ("before_cel_count", "before_cels", "affected_cels", "cel"):
        assert step[field] == expected[field]
    assert step["cel"]["position"] == {"x": -2, "y": 3}
    assert step["cel"]["opacity"] == 0
    assert step["cel"]["z_index"] == -1
    assert step["persisted_reopen_verified"] is False
    assert result["persisted_reopen_verified"] is True
    reopened = expect_success(
        "cel get", {"sprite_file": str(planned), "target": changes["target"]}
    )
    assert reopened["cel"] == expected["cel"]


def test_cel_set_resolves_a_cel_created_by_earlier_steps(tmp_path: Path) -> None:
    target = tmp_path / "created.aseprite"
    address = {"layer": {"layer_path": [1]}, "frame_number": 2}
    result = expect_success(
        "plan run",
        {
            "plan": {
                "target_sprite_file": str(target),
                "steps": [
                    {
                        "operation": "sprite create",
                        "input": {
                            "width": 4,
                            "height": 4,
                            "color_mode": "rgb",
                            "initial_layer": {"kind": "transparent"},
                        },
                    },
                    {
                        "operation": "paint apply",
                        "input": red_pixel(),
                    },
                    {
                        "operation": "sprite get",
                        "input": {"inspection_scope": ["cels"]},
                    },
                    {"operation": "frame list", "input": {}},
                    {"operation": "frame get", "input": {"frame_number": 1}},
                    {
                        "operation": "frame add",
                        "input": {"frame_number": 2, "duration_ms": 100},
                    },
                    {"operation": "cel add", "input": {"target": address}},
                    {
                        "operation": "cel set",
                        "input": {"target": address, "opacity": 0, "z_index": -3},
                    },
                    {
                        "operation": "frame duplicate",
                        "input": {"source_frame_number": 2, "cel_mode": "copy"},
                    },
                    {
                        "operation": "frame duplicate",
                        "input": {"source_frame_number": 2, "cel_mode": "link"},
                    },
                    {
                        "operation": "frame add",
                        "input": {"frame_number": 5, "duration_ms": 100},
                    },
                    {
                        "operation": "cel add",
                        "input": {
                            "target": {
                                "layer": {"layer_path": [1]},
                                "frame_number": 5,
                            }
                        },
                    },
                    {
                        "operation": "sprite get",
                        "input": {"inspection_scope": ["cels"]},
                    },
                ],
            },
        },
    )
    steps = result["steps"]
    assert steps[0]["result"]["sprite"]["metadata"]["cel_count"] == 1
    assert steps[2]["result"]["sprite"]["metadata"]["cel_count"] == 1
    assert steps[6]["result"]["before_cel_count"] == 1
    assert steps[7]["result"]["before_cel_count"] == 2
    assert steps[7]["result"]["cel"]["opacity"] == 0
    assert steps[8]["result"]["inserted_cel_count"] == 1
    assert steps[9]["result"]["inserted_cel_count"] == 1
    assert steps[10]["result"]["inserted_cel_count"] == 0
    assert steps[11]["result"]["before_cel_count"] == 4
    assert steps[12]["result"]["sprite"]["metadata"]["cel_count"] == 5
    assert result["final_sprite"]["metadata"]["cel_count"] == 5
    assert result["persisted_reopen_verified"] is True
    reopened = expect_success(
        "cel get", {"sprite_file": str(target), "target": address}
    )
    assert reopened["cel"]["exists"] is True
    assert reopened["cel"]["content"] == "transparent"
    assert reopened["cel"]["opacity"] == 0
    assert reopened["cel"]["z_index"] == -3


@pytest.mark.parametrize("in_place", [False, True])
def test_later_cel_refusal_reports_step_and_preserves_files(
    runtime: RuntimeObservation, tmp_path: Path, in_place: bool
) -> None:
    source = tmp_path / "source.aseprite"
    cel_relationships_sprite(runtime, source)
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(b"prior Target bytes")
    source_before, target_before = source.read_bytes(), target.read_bytes()
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    absent = {"layer": {"layer_path": [1]}, "frame_number": 2}

    outcome = run(
        "plan run",
        _cel_set_plan(
            source,
            target,
            [
                {"target": first, "opacity": 0},
                {"target": first, "position": {"x": -2, "y": 3}},
                {"target": absent, "z_index": 1},
            ],
        ),
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "cel_not_found"
    assert result["details"]["step_number"] == 3
    assert result["details"]["target"]["layer"]["layer_path"] == [1]
    assert result["details"]["target"]["frame_number"] == 2
    assert source.read_bytes() == source_before
    assert target.read_bytes() == target_before


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_plan_preserves_linked_pixels_on_hidden_locked_layers(
    tmp_path: Path, mode: str
) -> None:
    original = _image_fixture(tmp_path, mode)
    source = tmp_path / "hidden-locked.aseprite"
    expect_success(
        "layer set",
        {
            "source_sprite_file": str(original),
            "target_sprite_file": str(source),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1]},
            "properties": {"is_visible": False, "is_editable": False},
        },
    )
    before = _inspect(source, tmp_path)
    inputs = [
        {
            "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
            "position": {"x": -3, "y": 4},
            "opacity": 0,
        },
        {
            "target": {"layer": {"layer_name": "subject"}, "frame_number": 2},
            "z_index": -4,
        },
        {
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "position": None,
            "opacity": None,
            "z_index": 7,
        },
    ]
    current = source
    expected_steps = []
    for index, changes in enumerate(inputs):
        output = tmp_path / f"standalone-{index}.aseprite"
        result = expect_success(
            "cel set",
            {
                "source_sprite_file": str(current),
                "target_sprite_file": str(output),
                "in_place": False,
                "overwrite": False,
                **changes,
            },
        )
        expected_steps.append(result)
        current = output
    target = tmp_path / "planned.aseprite"

    result = expect_success("plan run", _cel_set_plan(source, target, inputs))
    validate(result, json.loads(spa("plan", "run", "--schema").stdout)["result_schema"])
    assert result["persisted_reopen_verified"] is True
    assert result["target_commit"]["target_sprite_file"] == str(target)
    for step, expected in zip(result["steps"], expected_steps, strict=True):
        assert step["result"]["persisted_reopen_verified"] is False
        for field in ("before_cel_count", "before_cels", "affected_cels", "cel"):
            assert step["result"][field] == expected[field]
    assert len(result["steps"][0]["result"]["affected_cels"]) == 2
    assert len(result["steps"][1]["result"]["affected_cels"]) == 1
    after = _inspect(target, tmp_path)
    assert after == _inspect(current, tmp_path)
    for old, new in zip(before["cels"], after["cels"], strict=True):
        assert new["pixels"] == old["pixels"]
        assert new["linked_frames"] == old["linked_frames"]
    assert after["cels"][0]["opacity"] == after["cels"][1]["opacity"] == 0
    assert [cel["z_index"] for cel in after["cels"][:2]] == [7, -4]
    assert after["cels"][2] == before["cels"][2]


@pytest.mark.parametrize(
    ("kind", "layer", "frame", "failure_code"),
    [
        ("background", 1, 1, "cel_unsupported_target"),
        ("reference", 1, 1, "cel_unsupported_target"),
        ("tilemap", 2, 1, "cel_unsupported_target"),
        ("group", 2, 1, "cel_unsupported_target"),
        ("absent", 1, 1, "cel_not_found"),
        ("regular", 9, 1, "layer_invalid_path"),
        ("regular", 1, 4, "cel_frame_out_of_bounds"),
    ],
)
def test_plan_retains_standalone_target_refusals(
    tmp_path: Path, kind: str, layer: int, frame: int, failure_code: str
) -> None:
    source = _image_fixture(tmp_path, kind=kind)
    target = tmp_path / "existing.aseprite"
    target.write_bytes(b"prior Target bytes")
    before = source.read_bytes()
    changes = {
        "target": {"layer": {"layer_path": [layer]}, "frame_number": frame},
        "opacity": 100,
    }
    outcome = run(
        "cel set",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            **changes,
        },
    )
    standalone = outcome.envelope
    assert outcome.returncode == 2, standalone
    assert standalone["code"] == failure_code

    outcome = run("plan run", _cel_set_plan(source, target, [changes]))
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == failure_code
    assert result["details"] == standalone["details"] | {"step_number": 1}
    validate(
        result, json.loads(spa("plan", "run", "--schema").stdout)["failure_schema"]
    )
    assert target.read_bytes() == b"prior Target bytes"
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    ("case", "operation", "in_place"),
    [
        ("success", "cel set", False),
        ("later_failure", "cel set", False),
        ("malformed_step", "cel set", False),
        ("unverified_save", "cel set", False),
    ]
    + [
        (case, operation, in_place)
        for case in ("contradictory_count", "contradictory_high_count")
        for operation in ("cel add", "cel set", "sprite get")
        for in_place in (False, True)
    ],
)
def test_cel_plan_has_one_native_invocation_and_gates_target_commit(
    runtime: RuntimeObservation,
    tmp_path: Path,
    case: str,
    operation: str,
    in_place: bool,
) -> None:
    source = tmp_path / "source.aseprite"
    cel_relationships_sprite(runtime, source)
    source_before = source.read_bytes()
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(b"prior Target bytes")
    target_before = target.read_bytes()
    second = 2 if case == "later_failure" else 1
    steps = [
        {
            "operation": "cel set",
            "input": {
                "target": {"layer": {"layer_path": [1]}, "frame_number": number},
                "opacity": opacity,
            },
        }
        for number, opacity in [(1, 0), (second, 100)]
    ]
    if operation == "cel add":
        steps[0] = {
            "operation": "cel add",
            "input": {"target": {"layer": {"layer_path": [1]}, "frame_number": 2}},
        }
    elif operation == "sprite get":
        steps[0] = {
            "operation": "sprite get",
            "input": {"inspection_scope": ["frames"]},
        }
    process, outcome, observations = observe_cli(
        FIXTURES / "observe_cli.py",
        case,
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": in_place,
                "overwrite": True,
                "steps": steps,
            },
        },
        tmp_path / "observations.json",
    )
    assert observations["native_invocations"] == 1
    assert source.read_bytes() == source_before
    assert not list(tmp_path.glob(".*.staged.aseprite"))
    if case == "success":
        assert process.returncode == 0, outcome
        assert outcome["persisted_reopen_verified"] is True
        assert observations["commits"] == 1
    else:
        assert process.returncode != 0, outcome
        assert outcome["code"] == (
            "cel_not_found" if case == "later_failure" else "kernel_response_invalid"
        )
        assert observations["commits"] == 0
        assert target.read_bytes() == target_before
        if case in ("contradictory_count", "contradictory_high_count"):
            assert outcome["details"]["failed_step"] == 1
            assert outcome["details"]["failed_operation"] == operation
