"""An Indexed erase uses the Sprite mask, even without a matching Palette Entry."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from tests.paint.support import call_spa

pytestmark = pytest.mark.e2e


def _native(**parameters: object) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    with tempfile.TemporaryDirectory(prefix="spa-eraser-mask-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        arguments = [str(prepared.executable), "--batch"]
        for name, value in parameters.items():
            arguments.extend(["--script-param", f"{name}={value}"])
        arguments.extend(
            [
                "--script",
                str(
                    Path(__file__).parent / "fixtures" / "eraser_transparent_index.lua"
                ),
            ]
        )
        run = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            env=prepared.environment,
            check=False,
        )
    assert run.returncode == 0, run.stdout + run.stderr


def _erase(source: Path, target: Path, *, frame: int = 1, **changes: object):
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
        "coordinate_space": "image-pixel",
        "points": [{"x": 1, "y": 0}],
        "freehand_algorithm": "regular",
        "brush": {"kind": "circle", "size": 1},
        "opacity": 255,
        "behavior": {"kind": "erase"},
    }
    return call_spa(
        "paint",
        "eraser",
        **(request | changes),
    )


@pytest.mark.parametrize("linked", [False, True])
def test_erase_uses_transparent_index_outside_effective_palette(
    tmp_path: Path, linked: bool
) -> None:
    source = tmp_path / "source.aseprite"
    reference = tmp_path / "native.aseprite"
    target = tmp_path / "erased.aseprite"
    _native(source=source, reference=reference, linked=str(linked).lower())
    original = source.read_bytes()

    code, result = _erase(source, target, frame=2 if linked else 1)

    assert code == 0, result
    assert result["native_behavior"] == "transparent-index"
    assert result["transparent_index"] == 7
    assert result["pixels_changed"] == 1
    assert result["effective_palettes"] == [
        {
            "frame_number": frame,
            "palette_frame_number": 1,
            "palette_size": 2,
            "indexes": [],
        }
        for frame in ([1, 2] if linked else [1])
    ]
    assert [cel["frame_number"] for cel in result["affected_cels"]] == (
        [1, 2] if linked else [1]
    )
    assert result["linked_cels_preserved"] and result["geometry_unchanged"]
    assert result["persisted_reopen_verified"]
    assert source.read_bytes() == original
    _native(reference=reference, target=target)


def test_eraser_still_rejects_missing_palette_backed_color(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _native(source=source, reference=tmp_path / "native.aseprite")
    original = source.read_bytes()
    target.write_bytes(original)

    code, result = _erase(
        source,
        target,
        overwrite=True,
        behavior={
            "kind": "replace-foreground-with-background",
            "foreground_color": {"kind": "palette-index", "index": 1},
            "background_color": {"kind": "palette-index", "index": 2},
        },
    )

    assert code == 1 and result["code"] == "kernel_execution_failed", result
    assert "Palette Index does not exist" in result["details"]["reason"]
    assert source.read_bytes() == target.read_bytes() == original
    assert not list(tmp_path.rglob("*.staged.aseprite"))
