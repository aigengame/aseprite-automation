"""Bounded real-native matrix: stored pixels, geometry, links, and document facts."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import ImageCms

from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _native(**params: object) -> None:
    binary = Path(os.environ["SPA_TEST_ASEPRITE"])
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    with tempfile.TemporaryDirectory(prefix="spa-cel-size-") as work:
        prepared = prepare_invocation(binary, resource, Path(work))
        args = [str(prepared.executable), "--batch"]
        for key, value in params.items():
            args.extend(["--script-param", f"{key}={value}"])
        args.extend(
            ["--script", str(Path(__file__).parent / "fixtures/image_size.lua")]
        )
        run = subprocess.run(
            args, text=True, capture_output=True, check=False, env=prepared.environment
        )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "Error" not in run.stdout + run.stderr, run.stdout + run.stderr


def _add(source: Path, target: Path, size: dict, *, plan: bool) -> dict:
    cel_input = {"target": {"layer": {"layer_path": [1]}, "frame_number": 3}, **size}
    files = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
    }
    if plan:
        command = ("plan", "run")
        request = {
            "plan": {**files, "steps": [{"operation": "cel add", "input": cel_input}]}
        }
    else:
        command = ("cel", "add")
        request = {**files, **cel_input}
    request["aseprite"] = os.environ["SPA_TEST_ASEPRITE"]
    run = spa(*command, "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["target_commit"]["target_sprite_file"] == str(target)
    assert result["persisted_reopen_verified"] is True
    return result["steps"][0]["result"]["cel"] if plan else result["cel"]


@pytest.mark.parametrize("plan", [False, True], ids=["standalone", "plan"])
@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed0", "indexed7"])
@pytest.mark.parametrize(
    "size",
    [
        {},
        {"image_size": None},
        *(
            {"image_size": {"width": width, "height": height}}
            for width, height in [(1, 1), (5, 5), (17, 13), (65535, 1), (1, 65535)]
        ),
    ],
    ids=[
        "omitted",
        "null",
        "single",
        "component",
        "overscan",
        "max-width",
        "max-height",
    ],
)
def test_add_preserves_native_document_and_initializes_every_pixel(
    tmp_path: Path, size: dict, mode: str, plan: bool
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "added.aseprite"
    _native(mode=mode, out=source)
    before = source.read_bytes()
    cel = _add(source, target, size, plan=plan)
    dimensions = size.get("image_size") or {"width": 8, "height": 6}
    assert cel["image_bounds"] == {"x": 0, "y": 0, **dimensions}
    assert cel["linked_cels"] == []
    _native(source=source, result=target, **dimensions)
    assert source.read_bytes() == before


def test_add_inherits_embedded_color_profile(tmp_path: Path) -> None:
    icc = tmp_path / "profile.icc"
    icc.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    source = tmp_path / "source.aseprite"
    target = tmp_path / "added.aseprite"
    _native(mode="rgb", out=source, icc=icc)
    size = {"width": 5, "height": 5}
    _add(source, target, {"image_size": size}, plan=False)
    _native(source=source, result=target, **size)
