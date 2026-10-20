"""Installed Operation Plan behavior through the public CLI."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from tests.native_invocation import expect_success, run
from tests.plan.support import red_pixel
from tests.support import isolated_wheel_cli, spa


@pytest.mark.e2e
def test_plan_run_reads_one_sprite_across_two_steps(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    result = expect_success(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "steps": [
                    {
                        "operation": "sprite get",
                        "input": {"inspection_scope": ["frames"]},
                    },
                    {
                        "operation": "sprite get",
                        "input": {"inspection_scope": ["layers"]},
                    },
                ],
            },
        },
    )
    assert result["target_commit"] is None
    assert [step["operation"] for step in result["steps"]] == [
        "sprite get",
        "sprite get",
    ]
    assert result["steps"][0]["result"]["sprite"]["frames"][0]["frame_number"] == 1
    assert result["steps"][1]["result"]["sprite"]["layers"][0]["path"] == [1]


@pytest.mark.e2e
def test_plan_run_creates_paints_and_commits_once(tmp_path: Path) -> None:
    target = tmp_path / "created.aseprite"
    result = expect_success(
        "plan run",
        {
            "plan": {
                "target_sprite_file": str(target),
                "steps": [
                    {
                        "operation": "sprite create",
                        "input": {
                            "width": 3,
                            "height": 2,
                            "color_mode": "rgb",
                            "initial_layer": {"kind": "transparent"},
                        },
                    },
                    {"operation": "paint apply", "input": red_pixel()},
                    {
                        "operation": "sprite get",
                        "input": {"inspection_scope": ["cels"]},
                    },
                ],
                "postconditions": {"width": 3, "height": 2, "frame_count": 1},
            },
        },
    )
    assert target.is_file()
    assert (
        result["target_commit"]["sha256"]
        == hashlib.sha256(target.read_bytes()).hexdigest()
    )
    assert result["persisted_reopen_verified"] is True
    assert result["steps"][1]["result"]["pixels_written"] == 1
    assert result["steps"][1]["result"]["persisted_reopen_verified"] is False
    assert result["steps"][2]["result"]["sprite"]["cels"]


@pytest.mark.e2e
def test_plan_failed_step_leaves_target_absent(tmp_path: Path) -> None:
    target = tmp_path / "step.aseprite"
    outcome = run(
        "plan run",
        {
            "plan": {
                "target_sprite_file": str(target),
                "steps": [
                    {
                        "operation": "sprite create",
                        "input": {
                            "width": 3,
                            "height": 2,
                            "color_mode": "rgb",
                            "initial_layer": {"kind": "transparent"},
                        },
                    },
                    {
                        "operation": "paint apply",
                        "input": {
                            **red_pixel(),
                            "target": {"layer_path": [9], "frame_number": 1},
                        },
                    },
                ],
            },
        },
    )
    failure = outcome.envelope
    assert outcome.returncode == 1, failure
    assert failure["code"] == "kernel_execution_failed"
    assert failure["details"]["failed_step"] == 2
    assert not target.exists()


@pytest.mark.e2e
def test_plan_failed_dynamic_postcondition_leaves_target_absent(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    target = tmp_path / "postcondition.aseprite"
    outcome = run(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "steps": [{"operation": "paint apply", "input": red_pixel()}],
                "postconditions": {"width": 99},
            },
        },
    )
    failure = outcome.envelope
    assert outcome.returncode == 1, failure
    assert failure["code"] == "kernel_execution_failed"
    assert failure["details"]["failed_step"] is None
    assert not target.exists()


@pytest.mark.e2e
def test_plan_in_place_failure_preserves_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    outcome = run(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(source),
                "in_place": True,
                "overwrite": True,
                "steps": [
                    {"operation": "paint apply", "input": red_pixel()},
                    {
                        "operation": "paint apply",
                        "input": {
                            **red_pixel(),
                            "target": {"layer_path": [9], "frame_number": 1},
                        },
                    },
                ],
            },
        },
    )
    failure = outcome.envelope
    assert outcome.returncode == 1, failure
    assert failure["details"]["failed_step"] == 2
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before

    result = expect_success(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(source),
                "in_place": True,
                "overwrite": True,
                "steps": [{"operation": "paint apply", "input": red_pixel()}],
            },
        },
    )
    assert result["target_commit"]["target_sprite_file"] == str(source)
    assert hashlib.sha256(source.read_bytes()).hexdigest() != before


@pytest.mark.e2e
def test_wheel_installed_plan_uses_packaged_handler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed_cli = isolated_wheel_cli(tmp_path, monkeypatch)
    target = tmp_path / "wheel-plan.aseprite"
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
                                "width": 2,
                                "height": 2,
                                "color_mode": "rgb",
                                "initial_layer": {"kind": "transparent"},
                            },
                        },
                        {
                            "operation": "cel set",
                            "input": {
                                "target": {
                                    "layer": {"layer_path": [1]},
                                    "frame_number": 1,
                                },
                                "opacity": 63,
                            },
                        },
                        {"operation": "paint apply", "input": red_pixel()},
                        {
                            "operation": "sprite get",
                            "input": {"inspection_scope": ["cels"]},
                        },
                    ],
                    "postconditions": {"width": 2, "height": 2, "frame_count": 1},
                },
            }
        ),
        executable=installed_cli,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert target.is_file()
    result = json.loads(run.stdout)
    assert result["persisted_reopen_verified"] is True
    assert result["steps"][1]["result"]["cel"]["opacity"] == 63
    assert result["steps"][2]["result"]["pixels_written"] == 1
    assert result["steps"][3]["result"]["sprite"]["cels"]
    assert (
        result["target_commit"]["sha256"]
        == hashlib.sha256(target.read_bytes()).hexdigest()
    )
