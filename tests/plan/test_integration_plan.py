"""Static Plan preflight through the installed CLI."""

import json
import os
import shlex
from pathlib import Path

from tests.support import fake_aseprite, spa


def _one_frame_inspection() -> dict[str, object]:
    return {
        "metadata": {
            "width": 1,
            "height": 1,
            "color_mode": "rgb",
            "frame_count": 1,
            "tag_count": 0,
            "palette_count": 0,
            "layer_count": 0,
            "cel_count": 0,
            "slice_count": 0,
            "tileset_count": 0,
            "transparent_color_index": 0,
            "grid_bounds": {"x": 0, "y": 0, "width": 1, "height": 1},
            "pixel_ratio": {"width": 1, "height": 1},
        },
        "frames": [{"frame_number": 1, "duration_ms": 100}],
        "tags": [],
        "palettes": [],
        "layers": [],
        "cels": [],
        "slices": [],
        "tilesets": [],
    }


def test_plan_check_admits_a_read_plan_without_launching_aseprite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"unused by static preflight")
    request = {
        "plan": {
            "source_sprite_file": str(source),
            "steps": [
                {"operation": "sprite get", "input": {"inspection_scope": ["frames"]}}
            ],
        }
    }
    environment = os.environ | {"SPA_ASEPRITE_EXECUTABLE": "/missing/aseprite"}

    run = spa("plan", "check", "--input-json", json.dumps(request), env=environment)

    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["operation"] == "spa plan check"
    assert result["step_count"] == 1
    assert result["commit_required"] is False


def test_plan_check_rejects_unknown_step_and_operation_owned_pixel_limit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"unused by static preflight")
    cases = [
        [{"operation": "export image", "input": {}}],
        [
            {
                "operation": "paint apply",
                "input": {
                    "target": {"layer_path": [1], "frame_number": 1},
                    "patch": {
                        "coordinate_space": "image-pixel",
                        "rectangle": {"x": 0, "y": 0, "width": 257, "height": 1},
                        "runs": [
                            {
                                "x": 0,
                                "y": 0,
                                "length": 257,
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
            }
        ],
        [
            {
                "operation": "paint apply",
                "input": {
                    "target": {"layer_path": [1], "frame_number": 1},
                    "patch": {
                        "coordinate_space": "image-pixel",
                        "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                        "runs": [
                            {
                                "x": 2,
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
            }
        ],
    ]
    for steps in cases:
        run = spa(
            "plan",
            "check",
            "--input-json",
            json.dumps(
                {
                    "plan": {
                        "source_sprite_file": str(source),
                        "target_sprite_file": str(tmp_path / "target.aseprite"),
                        "steps": steps,
                    },
                }
            ),
            env=os.environ | {"SPA_ASEPRITE_EXECUTABLE": "/missing/aseprite"},
        )
        assert run.returncode == 2, run.stdout
        assert json.loads(run.stdout)["code"] == "invalid_request"


def test_plan_step_limit_admits_the_issue_reference_size(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"unused by static preflight")
    steps = [{"operation": "sprite get", "input": {"inspection_scope": ["frames"]}}]
    for count, expected in ((42, 0), (65, 2)):
        run = spa(
            "plan",
            "check",
            "--input-json",
            json.dumps(
                {
                    "plan": {"source_sprite_file": str(source), "steps": steps * count},
                }
            ),
            env=os.environ | {"SPA_ASEPRITE_EXECUTABLE": "/missing/aseprite"},
        )
        assert run.returncode == expected, run.stdout


def test_plan_check_reports_decidable_path_failures_without_aseprite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    get = {"operation": "sprite get", "input": {"inspection_scope": ["frames"]}}
    create = {
        "operation": "sprite create",
        "input": {
            "width": 2,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
        },
    }
    cases = [
        {"source_sprite_file": str(source), "steps": [get]},
        {
            "target_sprite_file": str(tmp_path / "missing" / "target.aseprite"),
            "steps": [create],
        },
    ]
    target.write_bytes(b"existing target")
    cases.append({"target_sprite_file": str(target), "steps": [create]})
    for plan in cases:
        run = spa(
            "plan",
            "check",
            "--input-json",
            json.dumps({"plan": plan}),
            env=os.environ | {"SPA_ASEPRITE_EXECUTABLE": "/missing/aseprite"},
        )
        assert run.returncode == 2, run.stdout
        assert json.loads(run.stdout)["code"] == "invalid_request"


def test_plan_run_rejects_missing_source_before_aseprite_discovery(
    tmp_path: Path,
) -> None:
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": "/missing/aseprite",
                "plan": {
                    "source_sprite_file": str(tmp_path / "missing.aseprite"),
                    "steps": [
                        {
                            "operation": "sprite get",
                            "input": {"inspection_scope": ["frames"]},
                        }
                    ],
                },
            }
        ),
    )
    assert run.returncode == 2, run.stdout + run.stderr
    failure = json.loads(run.stdout)
    assert failure["code"] == "invalid_request"
    assert failure["details"]["errors"][0]["location"] == [
        "plan",
        "source_sprite_file",
    ]


def test_plan_preflight_checks_source_aliases_against_target_entry(
    tmp_path: Path,
) -> None:
    target = tmp_path / "real.aseprite"
    target.write_bytes(b"preflight only")
    alias = tmp_path / "alias.aseprite"
    alias.symlink_to(target)
    plan = {
        "source_sprite_file": str(alias),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
        "steps": [
            {
                "operation": "paint apply",
                "input": {
                    "target": {"layer_path": [1], "frame_number": 1},
                    "patch": {
                        "coordinate_space": "image-pixel",
                        "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                        "runs": [],
                    },
                },
            }
        ],
    }
    for command in ("check", "run"):
        request = {"plan": plan}
        if command == "run":
            request["aseprite"] = "/missing/aseprite"
        run = spa("plan", command, "--input-json", json.dumps(request))
        assert run.returncode == 2, run.stdout + run.stderr
        failure = json.loads(run.stdout)
        assert failure["code"] == "invalid_request"
        assert failure["details"]["errors"][0]["location"] == ["plan", "in_place"]

    target_alias = tmp_path / "target-alias.aseprite"
    target_alias.symlink_to(target)
    plan["source_sprite_file"] = str(target)
    plan["target_sprite_file"] = str(target_alias)
    accepted = spa("plan", "check", "--input-json", json.dumps({"plan": plan}))
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr

    source_through_target = tmp_path / "source-through-target.aseprite"
    source_through_target.symlink_to(target_alias)
    plan["source_sprite_file"] = str(source_through_target)

    for command in ("check", "run"):
        request = {"plan": plan}
        if command == "run":
            request["aseprite"] = "/missing/aseprite"
        result = spa("plan", command, "--input-json", json.dumps(request))
        assert result.returncode == 2, result.stdout + result.stderr
        failure = json.loads(result.stdout)
        assert failure["code"] == "invalid_request"
        assert failure["details"]["errors"][0]["location"] == ["plan", "in_place"]

    assert target_alias.is_symlink()
    assert source_through_target.read_bytes() == b"preflight only"


def test_plan_check_rejects_known_creation_postcondition_conflicts(
    tmp_path: Path,
) -> None:
    create = {
        "operation": "sprite create",
        "input": {
            "width": 2,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
        },
    }
    for conditions in (
        {"width": 3},
        {"height": 3},
        {"color_mode": "grayscale"},
        {"frame_count": 2},
    ):
        run = spa(
            "plan",
            "check",
            "--input-json",
            json.dumps(
                {
                    "plan": {
                        "target_sprite_file": str(tmp_path / "new.aseprite"),
                        "steps": [create],
                        "postconditions": conditions,
                    }
                }
            ),
            env=os.environ | {"SPA_ASEPRITE_EXECUTABLE": "/missing/aseprite"},
        )
        assert run.returncode == 2, run.stdout + run.stderr
        assert json.loads(run.stdout)["code"] == "invalid_request"


def test_plan_step_validation_reports_index_after_one_process(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"controlled transport fixture")
    count_file = tmp_path / "invocations.txt"
    response_file = tmp_path / "response.json"
    final_sprite = _one_frame_inspection()
    bad_step_sprite = final_sprite | {"frames": []}
    response_file.write_text(
        json.dumps(
            {
                "kernel_protocol_version": 1,
                "status": "ok",
                "result": {
                    "steps": [
                        {
                            "operation": "sprite get",
                            "result": {
                                "sprite": bad_step_sprite,
                            },
                        }
                    ],
                    "final_sprite": final_sprite,
                    "persisted_reopen_verified": False,
                },
            }
        ),
        encoding="utf-8",
    )
    fake = fake_aseprite(
        tmp_path,
        f"""
response_file=
for argument in "$@"; do
  case "$argument" in response=*) response_file=${{argument#response=}};; esac
done
printf '1\\n' >> {shlex.quote(str(count_file))}
cp {shlex.quote(str(response_file))} "$response_file"
""",
    )
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": str(fake),
                "plan": {
                    "source_sprite_file": str(source),
                    "steps": [
                        {
                            "operation": "sprite get",
                            "input": {"inspection_scope": ["frames"]},
                        }
                    ],
                },
            }
        ),
    )
    assert run.returncode == 1, run.stdout + run.stderr
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_invalid"
    assert failure["details"]["failed_step"] == 1
    assert failure["details"]["failed_operation"] == "sprite get"
    assert count_file.read_text(encoding="utf-8").splitlines() == ["1"]


def test_plan_create_postcondition_failure_identifies_step(tmp_path: Path) -> None:
    target = tmp_path / "target.aseprite"
    response_file = tmp_path / "create-response.json"
    final_sprite = _one_frame_inspection()
    response_file.write_text(
        json.dumps(
            {
                "kernel_protocol_version": 1,
                "status": "ok",
                "result": {
                    "steps": [
                        {
                            "operation": "sprite create",
                            "result": {
                                "sprite": final_sprite,
                                "initial_layer": {"kind": "transparent"},
                            },
                        }
                    ],
                    "final_sprite": final_sprite,
                    "persisted_reopen_verified": True,
                },
            }
        ),
        encoding="utf-8",
    )
    fake = fake_aseprite(
        tmp_path,
        f"""
response_file=
for argument in "$@"; do
  case "$argument" in response=*) response_file=${{argument#response=}};; esac
done
cp {shlex.quote(str(response_file))} "$response_file"
""",
    )
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": str(fake),
                "plan": {
                    "target_sprite_file": str(target),
                    "steps": [
                        {
                            "operation": "sprite create",
                            "input": {
                                "width": 2,
                                "height": 1,
                                "color_mode": "rgb",
                                "initial_layer": {"kind": "transparent"},
                            },
                        }
                    ],
                },
            }
        ),
    )
    assert run.returncode == 1, run.stdout + run.stderr
    failure = json.loads(run.stdout)
    assert failure["code"] == "kernel_response_invalid"
    assert failure["details"]["failed_step"] == 1
    assert failure["details"]["failed_operation"] == "sprite create"
    assert not target.exists()


def test_plan_runtime_capability_failure_is_typed_before_steps(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"controlled transport fixture")
    response_file = tmp_path / "runtime-response.json"
    response_file.write_text(
        json.dumps(
            {
                "kernel_protocol_version": 1,
                "status": "error",
                "cause": "runtime_incompatible",
                "message": "Plan runtime does not meet Step requirements",
                "runtime_compatibility": {
                    "aseprite_version": "test",
                    "lua_version": "Lua 5.4",
                    "api_version": 41,
                    "required_lua_language": "Lua 5.4",
                    "minimum_api_version": 41,
                    "missing_capabilities": ["aseprite_sprite_inspection"],
                },
            }
        ),
        encoding="utf-8",
    )
    fake = fake_aseprite(
        tmp_path,
        f"""
response_file=
for argument in "$@"; do
  case "$argument" in response=*) response_file=${{argument#response=}};; esac
done
cp {shlex.quote(str(response_file))} "$response_file"
""",
    )
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": str(fake),
                "plan": {
                    "source_sprite_file": str(source),
                    "steps": [
                        {
                            "operation": "sprite get",
                            "input": {"inspection_scope": ["frames"]},
                        }
                    ],
                },
            }
        ),
    )
    assert run.returncode == 1, run.stdout + run.stderr
    failure = json.loads(run.stdout)
    assert failure["code"] == "runtime_incompatible"
    assert failure["details"]["missing_capabilities"] == ["aseprite_sprite_inspection"]
