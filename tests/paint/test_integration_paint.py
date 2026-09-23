"""Public Paint request validation without a running Aseprite executable."""

import json
from pathlib import Path

import pytest

from tests.support import spa


@pytest.mark.parametrize("in_place", [False, True])
def test_apply_rejects_source_alias_before_runtime_probe(
    tmp_path: Path, in_place: bool
) -> None:
    target = tmp_path / "target.aseprite"
    target.write_bytes(b"unchanged")
    source = tmp_path / "source.aseprite"
    source.symlink_to(target)
    request = {
        "aseprite": "/missing/aseprite",
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": in_place,
        "overwrite": True,
        "target": {"layer_path": [1], "frame_number": 1},
        "patch": {
            "coordinate_space": "image-pixel",
            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
            "runs": [],
        },
    }

    run = spa("paint", "apply", "--input-json", json.dumps(request))

    assert run.returncode == 2, run.stdout + run.stderr
    assert json.loads(run.stdout)["code"] == "invalid_request"
    assert source.is_symlink()
    assert source.read_bytes() == b"unchanged"


@pytest.mark.parametrize("in_place", [False, True])
def test_apply_rejects_intent_that_disagrees_with_publication_entry(
    tmp_path: Path, in_place: bool
) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"unchanged")
    target = tmp_path / "target.aseprite" if in_place else source
    request = {
        "aseprite": "/missing/aseprite",
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": in_place,
        "overwrite": True,
        "target": {"layer_path": [1], "frame_number": 1},
        "patch": {
            "coordinate_space": "image-pixel",
            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
            "runs": [],
        },
    }

    run = spa("paint", "apply", "--input-json", json.dumps(request))

    assert run.returncode == 2, run.stdout + run.stderr
    failure = json.loads(run.stdout)
    assert failure["code"] == "invalid_request"
    assert failure["details"]["errors"][0]["location"] == ["in_place"]
    assert source.read_bytes() == b"unchanged"
