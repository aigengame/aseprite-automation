"""Cel existence and lifecycle through the installed CLI and real Aseprite."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

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
