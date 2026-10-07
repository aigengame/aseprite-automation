"""Installed Operation Plan behavior through the public CLI."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from tests.support import spa


@pytest.mark.e2e
def test_plan_run_reads_one_sprite_across_two_steps(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    create = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(
            {
                "target_sprite_file": str(source),
                "width": 3,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {"kind": "transparent"},
                "overwrite": False,
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert create.returncode == 0, create.stdout
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
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
            }
        ),
    )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["target_commit"] is None
    assert [step["operation"] for step in result["steps"]] == [
        "sprite get",
        "sprite get",
    ]
    assert result["steps"][0]["result"]["sprite"]["frames"][0]["frame_number"] == 1
    assert result["steps"][1]["result"]["sprite"]["layers"][0]["path"] == [1]


def _red_pixel(x: int = 0) -> dict[str, object]:
    return {
        "target": {"layer_path": [1], "frame_number": 1},
        "patch": {
            "coordinate_space": "image-pixel",
            "rectangle": {"x": x, "y": 0, "width": 1, "height": 1},
            "runs": [
                {
                    "x": x,
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
    }


@pytest.mark.e2e
def test_plan_run_creates_paints_and_commits_once(tmp_path: Path) -> None:
    target = tmp_path / "created.aseprite"
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
                                "width": 3,
                                "height": 2,
                                "color_mode": "rgb",
                                "initial_layer": {"kind": "transparent"},
                            },
                        },
                        {"operation": "paint apply", "input": _red_pixel()},
                        {
                            "operation": "sprite get",
                            "input": {"inspection_scope": ["cels"]},
                        },
                    ],
                    "postconditions": {"width": 3, "height": 2, "frame_count": 1},
                },
            }
        ),
    )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
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
                                "width": 3,
                                "height": 2,
                                "color_mode": "rgb",
                                "initial_layer": {"kind": "transparent"},
                            },
                        },
                        {
                            "operation": "paint apply",
                            "input": {
                                **_red_pixel(),
                                "target": {"layer_path": [9], "frame_number": 1},
                            },
                        },
                    ],
                },
            }
        ),
    )
    assert run.returncode == 1, run.stdout + run.stderr
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_execution_failed"
    assert failure["details"]["failed_step"] == 2
    assert not target.exists()


@pytest.mark.e2e
def test_plan_failed_dynamic_postcondition_leaves_target_absent(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    created = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(
            {
                "target_sprite_file": str(source),
                "width": 3,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {"kind": "transparent"},
                "overwrite": False,
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert created.returncode == 0, created.stdout + created.stderr
    target = tmp_path / "postcondition.aseprite"
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
                    "steps": [{"operation": "paint apply", "input": _red_pixel()}],
                    "postconditions": {"width": 99},
                },
            }
        ),
    )
    assert run.returncode == 1, run.stdout + run.stderr
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_execution_failed"
    assert failure["details"]["failed_step"] is None
    assert not target.exists()


@pytest.mark.e2e
def test_plan_in_place_failure_preserves_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    create = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(
            {
                "target_sprite_file": str(source),
                "width": 3,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {"kind": "transparent"},
                "overwrite": False,
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert create.returncode == 0, create.stdout
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "plan": {
                    "source_sprite_file": str(source),
                    "target_sprite_file": str(source),
                    "in_place": True,
                    "overwrite": True,
                    "steps": [
                        {"operation": "paint apply", "input": _red_pixel()},
                        {
                            "operation": "paint apply",
                            "input": {
                                **_red_pixel(),
                                "target": {"layer_path": [9], "frame_number": 1},
                            },
                        },
                    ],
                },
            }
        ),
    )
    assert run.returncode == 1, run.stdout + run.stderr
    failure = json.loads(run.stdout)
    assert failure["details"]["failed_step"] == 2
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before

    success = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "plan": {
                    "source_sprite_file": str(source),
                    "target_sprite_file": str(source),
                    "in_place": True,
                    "overwrite": True,
                    "steps": [{"operation": "paint apply", "input": _red_pixel()}],
                },
            }
        ),
    )
    assert success.returncode == 0, success.stdout + success.stderr
    result = json.loads(success.stdout)
    assert result["target_commit"]["target_sprite_file"] == str(source)
    assert hashlib.sha256(source.read_bytes()).hexdigest() != before


@pytest.mark.e2e
def test_source_alias_is_rejected_for_both_in_place_values(
    tmp_path: Path,
) -> None:
    target = tmp_path / "real.aseprite"
    created = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(
            {
                "target_sprite_file": str(target),
                "width": 2,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {"kind": "transparent"},
                "overwrite": False,
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert created.returncode == 0, created.stdout + created.stderr
    alias = tmp_path / "alias.aseprite"
    alias.symlink_to(target)
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    plan = {
        "source_sprite_file": str(alias),
        "target_sprite_file": str(target),
        "overwrite": True,
        "steps": [{"operation": "paint apply", "input": _red_pixel()}],
    }
    for in_place in (False, True):
        rejected = spa(
            "plan",
            "run",
            "--input-json",
            json.dumps(
                {
                    "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                    "plan": plan | {"in_place": in_place},
                }
            ),
        )
        assert rejected.returncode == 2, rejected.stdout + rejected.stderr
        failure = json.loads(rejected.stdout)
        assert failure["code"] == "invalid_request"
        assert failure["details"]["errors"][0]["location"] == [
            "plan",
            "source_sprite_file",
        ]
        assert hashlib.sha256(target.read_bytes()).hexdigest() == before
        assert alias.is_symlink()


@pytest.mark.e2e
def test_wheel_installed_plan_uses_packaged_handler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed_cli = os.environ.get("SPA_TEST_INSTALLED_CLI")
    if installed_cli is None:
        pytest.skip("SPA_TEST_INSTALLED_CLI does not select a wheel-installed CLI")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTHONPATH", raising=False)
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
                        {"operation": "paint apply", "input": _red_pixel()},
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
