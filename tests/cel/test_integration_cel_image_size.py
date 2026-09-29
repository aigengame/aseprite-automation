"""Image size request validation must precede any runtime or file mutation."""

import json
from pathlib import Path

import pytest

from tests.support import spa


@pytest.mark.parametrize("operation", ["add", "plan"])
@pytest.mark.parametrize(
    "image_size",
    [
        {},
        {"width": 1},
        {"height": 1},
        {"width": True, "height": 1},
        {"width": 1, "height": False},
        {"width": 1.5, "height": 1},
        {"width": 1, "height": 2.5},
        {"width": 0, "height": 1},
        {"width": 1, "height": -1},
        {"width": 65536, "height": 1},
        {"width": 1, "height": 65536},
        {"width": "2", "height": 1},
        {"width": 1, "height": 1, "unknown": True},
    ],
)
def test_invalid_size_is_rejected_before_runtime(
    tmp_path: Path, operation: str, image_size: dict
) -> None:
    _reject(tmp_path, operation, image_size)


@pytest.mark.parametrize("operation", ["clear", "remove"])
@pytest.mark.parametrize("image_size", [None, {"width": 1, "height": 1}])
def test_image_size_is_exclusive_to_add(
    tmp_path: Path, operation: str, image_size: dict | None
) -> None:
    _reject(tmp_path, operation, image_size)


def _reject(tmp_path: Path, operation: str, image_size: dict | None) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    source.write_bytes(b"Source must remain unchanged")
    target.write_bytes(b"Target must remain unchanged")
    cel_input = {
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "image_size": image_size,
    }
    files = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
    }
    if operation == "plan":
        command = ("plan", "run")
        request = {
            "plan": {**files, "steps": [{"operation": "cel add", "input": cel_input}]}
        }
    else:
        command = ("cel", operation)
        request = {**files, **cel_input}
    request["aseprite"] = "/missing/aseprite"
    run = spa(*command, "--input-json", json.dumps(request))
    assert run.returncode == 2, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["code"] == "invalid_request", result
    assert any(
        "image_size" in error["location"] for error in result["details"]["errors"]
    )
    assert source.read_bytes() == b"Source must remain unchanged"
    assert target.read_bytes() == b"Target must remain unchanged"
