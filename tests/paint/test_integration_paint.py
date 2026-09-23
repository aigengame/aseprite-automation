"""Public Paint request validation without a running Aseprite executable."""

import json
from pathlib import Path

from tests.support import spa


def test_apply_rejects_source_alias_before_runtime_probe(tmp_path: Path) -> None:
    target = tmp_path / "target.aseprite"
    target.write_bytes(b"unchanged")
    source = tmp_path / "source.aseprite"
    source.symlink_to(target)
    request = {
        "aseprite": "/missing/aseprite",
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
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
