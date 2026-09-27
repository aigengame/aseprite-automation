"""Existing Cel property semantics composed in a bounded Operation Plan."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import validate

from tests.cel.test_e2e_cel import _fixture, _run
from tests.image.test_e2e_image_orientation import _fixture as _image_fixture
from tests.image.test_e2e_image_orientation import _inspect
from tests.layer.test_e2e_layer_mutation import _run as _run_layer
from tests.support import spa

pytestmark = pytest.mark.e2e


def _plan(source: Path, target: Path, inputs: list[dict]) -> tuple[int, dict]:
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "plan": {
                    "source_sprite_file": str(source),
                    "target_sprite_file": str(target),
                    "in_place": source == target,
                    "overwrite": target.exists(),
                    "steps": [
                        {"operation": "cel set", "input": value} for value in inputs
                    ],
                },
            }
        ),
    )
    assert run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)


def test_cel_set_plan_matches_standalone_and_defers_persistence(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    standalone = tmp_path / "standalone.aseprite"
    planned = tmp_path / "planned.aseprite"
    _fixture(source, "relationships.lua")
    changes = {
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "position": {"x": -2, "y": 3},
        "opacity": 0,
        "z_index": -1,
    }
    code, expected = _run(
        "set",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(standalone),
            "in_place": False,
            "overwrite": False,
            **changes,
        },
    )
    assert code == 0, expected

    code, result = _plan(source, planned, [changes])

    assert code == 0, result
    step = result["steps"][0]["result"]
    for field in ("before_cel_count", "before_cels", "affected_cels", "cel"):
        assert step[field] == expected[field]
    assert step["cel"]["position"] == {"x": -2, "y": 3}
    assert step["cel"]["opacity"] == 0
    assert step["cel"]["z_index"] == -1
    assert step["persisted_reopen_verified"] is False
    assert result["persisted_reopen_verified"] is True
    code, reopened = _run(
        "get", {"sprite_file": str(planned), "target": changes["target"]}
    )
    assert code == 0, reopened
    assert reopened["cel"] == expected["cel"]


def test_cel_set_resolves_a_cel_created_by_earlier_steps(tmp_path: Path) -> None:
    target = tmp_path / "created.aseprite"
    address = {"layer": {"layer_path": [1]}, "frame_number": 2}
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
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
                            "operation": "frame add",
                            "input": {"frame_number": 2, "duration_ms": 100},
                        },
                        {"operation": "cel add", "input": {"target": address}},
                        {
                            "operation": "cel set",
                            "input": {"target": address, "opacity": 0, "z_index": -3},
                        },
                        {
                            "operation": "frame add",
                            "input": {"frame_number": 3, "duration_ms": 100},
                        },
                        {
                            "operation": "cel add",
                            "input": {
                                "target": {
                                    "layer": {"layer_path": [1]},
                                    "frame_number": 3,
                                }
                            },
                        },
                    ],
                },
            }
        ),
    )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["steps"][3]["result"]["cel"]["opacity"] == 0
    assert (
        result["final_sprite"]["metadata"]["cel_count"]
        == result["steps"][3]["result"]["before_cel_count"] + 1
    )
    assert result["persisted_reopen_verified"] is True
    code, reopened = _run("get", {"sprite_file": str(target), "target": address})
    assert code == 0, reopened
    assert reopened["cel"]["exists"] is True
    assert reopened["cel"]["content"] == "transparent"
    assert reopened["cel"]["opacity"] == 0
    assert reopened["cel"]["z_index"] == -3


@pytest.mark.parametrize("in_place", [False, True])
def test_later_cel_refusal_reports_step_and_preserves_files(
    tmp_path: Path, in_place: bool
) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, "relationships.lua")
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(b"prior Target bytes")
    source_before, target_before = source.read_bytes(), target.read_bytes()
    first = {"layer": {"layer_path": [1]}, "frame_number": 1}
    absent = {"layer": {"layer_path": [1]}, "frame_number": 2}

    code, result = _plan(
        source,
        target,
        [
            {"target": first, "opacity": 0},
            {"target": first, "position": {"x": -2, "y": 3}},
            {"target": absent, "z_index": 1},
        ],
    )

    assert code == 2, result
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
    code, setup = _run_layer(
        "set",
        {
            "source_sprite_file": str(original),
            "target_sprite_file": str(source),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1]},
            "properties": {"is_visible": False, "is_editable": False},
        },
    )
    assert code == 0, setup
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
        code, result = _run(
            "set",
            {
                "source_sprite_file": str(current),
                "target_sprite_file": str(output),
                "in_place": False,
                "overwrite": False,
                **changes,
            },
        )
        assert code == 0, result
        expected_steps.append(result)
        current = output
    target = tmp_path / "planned.aseprite"

    code, result = _plan(source, target, inputs)

    assert code == 0, result
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
    code, standalone = _run(
        "set",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            **changes,
        },
    )
    assert code == 2, standalone
    assert standalone["code"] == failure_code

    code, result = _plan(source, target, [changes])

    assert code == 2, result
    assert result["code"] == failure_code
    assert result["details"] == standalone["details"] | {"step_number": 1}
    validate(
        result, json.loads(spa("plan", "run", "--schema").stdout)["failure_schema"]
    )
    assert target.read_bytes() == b"prior Target bytes"
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "case",
    [
        "success",
        "later_failure",
        "malformed_step",
        "contradictory_count",
        "unverified_save",
    ],
)
def test_cel_plan_has_one_native_invocation_and_gates_target_commit(
    tmp_path: Path, case: str
) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, "relationships.lua")
    source_before = source.read_bytes()
    target = tmp_path / "existing.aseprite"
    target.write_bytes(b"prior Target bytes")
    second = 2 if case == "later_failure" else 1
    request = json.dumps(
        {
            "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": True,
                "steps": [
                    {
                        "operation": "cel set",
                        "input": {
                            "target": {
                                "layer": {"layer_path": [1]},
                                "frame_number": number,
                            },
                            "opacity": opacity,
                        },
                    }
                    for number, opacity in [(1, 0), (second, 100)]
                ],
            },
        }
    )
    cli = shutil.which("spa")
    assert cli, "run tests in an installed SPA environment"
    observations_file = tmp_path / "observations.json"
    run = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "fixtures" / "observe_cli.py"),
            case,
            str(observations_file),
            cli,
            "plan",
            "run",
            "--input-json",
            request,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.stdout, run.stderr
    outcome = json.loads(run.stdout)
    observations = json.loads(observations_file.read_text())
    assert observations["native_invocations"] == 1
    assert source.read_bytes() == source_before
    assert not list(tmp_path.glob(".*.staged.aseprite"))
    if case == "success":
        assert run.returncode == 0, outcome
        assert outcome["persisted_reopen_verified"] is True
        assert observations["commits"] == 1
    else:
        assert run.returncode != 0, outcome
        assert outcome["code"] == (
            "cel_not_found" if case == "later_failure" else "kernel_response_invalid"
        )
        assert observations["commits"] == 0
        assert target.read_bytes() == b"prior Target bytes"
        if case == "contradictory_count":
            assert outcome["details"]["failed_step"] == 1
            assert outcome["details"]["failed_operation"] == "cel set"
