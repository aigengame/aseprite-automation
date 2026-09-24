"""Cel existence and lifecycle through the installed CLI and real Aseprite."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _fixture(target: Path, name: str = "cels.lua") -> None:
    binary = Path(os.environ["SPA_TEST_ASEPRITE"])
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    with tempfile.TemporaryDirectory(prefix="spa-cel-fixture-") as work:
        prepared = prepare_invocation(binary, resource, Path(work))
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={target}",
                "--script",
                str(Path(__file__).parent / "fixtures" / name),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr


def _run(command: str, request: dict[str, object]) -> tuple[int, dict]:
    payload = {**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}
    run = spa("cel", command, "--input-json", json.dumps(payload))
    assert run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)


def test_list_distinguishes_absent_transparent_and_nonempty_cels(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source)
    code, listing = _run(
        "list",
        {
            "sprite_file": str(source),
            "layer": {"layer_path": [1]},
            "from_frame": 1,
            "to_frame": 3,
        },
    )
    assert code == 0, json.dumps(listing, indent=2)
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


def test_add_and_remove_preserve_explicit_cel_existence(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    added_file = tmp_path / "added.aseprite"
    removed_file = tmp_path / "removed.aseprite"
    _fixture(source)
    target = {"layer": {"layer_path": [1]}, "frame_number": 1}
    code, absent = _run("get", {"sprite_file": str(source), "target": target})
    assert code == 0, absent
    assert absent["cel"]["exists"] is False

    code, added = _run(
        "add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(added_file),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    assert code == 0, added
    assert added["persisted_reopen_verified"] is True
    assert added["cel"]["content"] == "transparent"
    code, reopened = _run("get", {"sprite_file": str(added_file), "target": target})
    assert code == 0, reopened
    assert reopened["cel"] == added["cel"]

    collision = tmp_path / "collision.aseprite"
    code, failure = _run(
        "add",
        {
            "source_sprite_file": str(added_file),
            "target_sprite_file": str(collision),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    assert code == 2, failure
    assert failure["code"] == "cel_already_exists"
    assert not collision.exists()

    code, removed = _run(
        "remove",
        {
            "source_sprite_file": str(added_file),
            "target_sprite_file": str(removed_file),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    assert code == 0, removed
    assert removed["cel"]["exists"] is False
    code, reopened = _run("get", {"sprite_file": str(removed_file), "target": target})
    assert code == 0, reopened
    assert reopened["cel"] == removed["cel"]

    missing = tmp_path / "missing.aseprite"
    code, failure = _run(
        "remove",
        {
            "source_sprite_file": str(removed_file),
            "target_sprite_file": str(missing),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    assert code == 2, failure
    assert failure["code"] == "cel_not_found"
    assert not missing.exists()


@pytest.mark.parametrize("number", [1, 2, 3])
def test_background_cel_clear_requires_explicit_color_at_each_frame(
    tmp_path: Path, number: int
) -> None:
    source = tmp_path / "background.aseprite"
    target_file = tmp_path / "cleared.aseprite"
    _fixture(source, "background.lua")
    target = {"layer": {"layer_path": [1]}, "frame_number": number}
    common = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target_file),
        "in_place": False,
        "overwrite": False,
        "target": target,
    }
    for operation in ("add", "remove"):
        code, failure = _run(operation, common)
        assert code == 2, failure
        assert failure["code"] == "cel_unsupported_target"
        assert not target_file.exists()
    code, failure = _run("clear", common)
    assert code == 2, failure
    assert failure["code"] == "cel_background_color_required"
    assert not target_file.exists()

    color = {"kind": "rgba", "red": 3, "green": 7, "blue": 11, "alpha": 255}
    code, cleared = _run("clear", {**common, "background_color": color})
    assert code == 0, cleared
    assert cleared["cel"]["exists"] is True
    assert cleared["cel"]["is_background"] is True
    assert cleared["cel"]["image_bounds"] == {
        "x": 0,
        "y": 0,
        "width": 4,
        "height": 3,
    }
    assert cleared["persisted_reopen_verified"] is True
    code, reopened = _run("get", {"sprite_file": str(target_file), "target": target})
    assert code == 0, reopened
    assert reopened["cel"] == cleared["cel"]
    artifact = tmp_path / "frame.png"
    export = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(
            {
                "source_sprite_file": str(target_file),
                "destination": {"path": str(artifact), "if_exists": "fail"},
                "frame_number": number,
                "color_mode": "preserve",
                "color_profile": "preserve",
                "transparency": "preserve",
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert export.returncode == 0, export.stdout
    with Image.open(artifact) as rendered:
        rgba = rendered.convert("RGBA")
        assert all(
            rgba.getpixel((x, y)) == (3, 7, 11, 255)
            for y in range(rgba.height)
            for x in range(rgba.width)
        )


def test_get_reports_native_linked_cels_after_reopen(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    linked_file = tmp_path / "linked.aseprite"
    _fixture(source)
    run = spa(
        "frame",
        "duplicate",
        "--input-json",
        json.dumps(
            {
                "source_sprite_file": str(source),
                "target_sprite_file": str(linked_file),
                "in_place": False,
                "overwrite": False,
                "source_frame_number": 3,
                "cel_mode": "link",
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    for number, other in ((3, 4), (4, 3)):
        code, result = _run(
            "get",
            {
                "sprite_file": str(linked_file),
                "target": {"layer": {"layer_path": [1]}, "frame_number": number},
            },
        )
        assert code == 0, result
        assert result["cel"]["content"] == "nonempty"
        assert result["cel"]["linked_cels"] == [
            {"layer_path": [1], "frame_number": other}
        ]


def test_plan_adds_cel_then_paints_it_in_one_commit(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "painted.aseprite"
    _fixture(source)
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
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
                        }
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
    run = spa("plan", "run", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["persisted_reopen_verified"] is True
    assert [step["operation"] for step in result["steps"]] == [
        "cel add",
        "paint apply",
    ]
    assert result["steps"][0]["result"]["cel"]["content"] == "transparent"
    code, reopened = _run(
        "get",
        {
            "sprite_file": str(target_file),
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        },
    )
    assert code == 0, reopened
    assert reopened["cel"]["content"] == "nonempty"


def test_paint_requires_existing_cel_and_does_not_create_one(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "painted.aseprite"
    _fixture(source)
    run = spa(
        "paint",
        "apply",
        "--input-json",
        json.dumps(
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
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert run.returncode == 2, run.stdout
    assert json.loads(run.stdout)["code"] == "cel_not_found"
    assert not target_file.exists()


def test_clear_preserves_regular_cel_and_image_bounds(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "cleared.aseprite"
    _fixture(source)
    target = {"layer": {"layer_path": [1]}, "frame_number": 3}
    code, cleared = _run(
        "clear",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target_file),
            "in_place": False,
            "overwrite": False,
            "target": target,
        },
    )
    assert code == 0, cleared
    assert cleared["before"]["content"] == "nonempty"
    assert cleared["cel"]["content"] == "transparent"
    assert cleared["cel"]["exists"] is True
    assert cleared["cel"]["image_bounds"] == cleared["before"]["image_bounds"]
    code, reopened = _run("get", {"sprite_file": str(target_file), "target": target})
    assert code == 0, reopened
    assert reopened["cel"] == cleared["cel"]


def test_plan_paint_without_cel_fails_with_typed_outcome(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "painted.aseprite"
    _fixture(source)
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
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
            }
        ),
    )
    assert run.returncode == 2, run.stdout
    assert json.loads(run.stdout)["code"] == "cel_not_found"
    assert not target_file.exists()


def test_plan_duplicate_cel_add_rejects_without_commit(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target_file = tmp_path / "duplicate.aseprite"
    _fixture(source)
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "plan": {
                    "source_sprite_file": str(source),
                    "target_sprite_file": str(target_file),
                    "steps": [
                        {
                            "operation": "cel add",
                            "input": {
                                "target": {
                                    "layer": {"layer_path": [1]},
                                    "frame_number": 2,
                                }
                            },
                        }
                    ],
                },
            }
        ),
    )
    assert run.returncode == 2, run.stdout
    failure = json.loads(run.stdout)
    assert failure["code"] == "cel_already_exists"
    assert failure["details"]["step_number"] == 1
    assert not target_file.exists()
