"""Sprite builders, PNG writers and publication seams shared by the import tests.

The directory name `import` is a Python keyword, so test modules import this
module with a relative import.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png_input import decode_png_input
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.authoring.raster.image_import import IMAGE_IMPORT_OPERATIONS
from spa.contracts.ports import OperationServices, RuntimeObservation
from tests.native_invocation import run_lua
from tests.support import process_diagnostics

FIXTURES = Path(__file__).parent / "fixtures"


def import_target(runtime: RuntimeObservation, source: Path, **params: str) -> None:
    """Write the `import_target.lua` Sprite to source.

    The params select the Color Mode, the profile, the Palette and the target Cel.
    """
    lua = run_lua(FIXTURES / "import_target.lua", runtime, out=source, **params)
    assert lua.returncode == 0, process_diagnostics(lua)


def indexed_png(
    path: Path,
    indexes: list[int],
    *,
    colors: list[tuple[int, int, int]] | None = None,
    alpha: bytes | None = b"\x00\xff\x80\xff",
) -> None:
    """Write one row of palette indexes as an 8-bit Indexed PNG with tRNS alpha."""
    entries = colors or [(0, 0, 0), (200, 20, 40), (10, 80, 160), (17, 31, 53)]
    image = Image.new("P", (len(indexes), 1))
    image.putpalette([component for entry in entries for component in entry])
    image.putdata(indexes)
    image.save(path, bits=8, transparency=alpha)


class ObservedTargetFiles(LocalTargetFiles):
    """Local target files that record each stage, commit and discard."""

    def __init__(self) -> None:
        self.stages: list[Path] = []
        self.commits: list[Path] = []
        self.discards: list[Path] = []

    def staged_path(self, target):
        staged = super().staged_path(target)
        self.stages.append(staged)
        return staged

    def commit(self, staged, target, *, overwrite):
        self.commits.append(staged)
        return super().commit(staged, target, overwrite=overwrite)

    def discard(self, staged):
        self.discards.append(staged)
        super().discard(staged)


def dispatch_import(
    source: Path,
    raster: Path,
    target: Path,
    runtime: RuntimeObservation,
    files: LocalTargetFiles,
    invoker: Callable[..., Any],
) -> dict[str, Any]:
    """Run `image import` in process with the given target files and Kernel invoker.

    The request places raster at (-1, 1) on Layer 1, Frame 2, and replaces target.
    The probe returns runtime.
    """
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
        "raster_file": str(raster),
        "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
        "position": {"x": -1, "y": 1},
    }
    services = OperationServices(
        probe_runtime=lambda _: runtime,
        invoke_kernel=invoker,
        target_files=files,
        artifact_files=LocalArtifactFiles(),
        decode_png_input=decode_png_input,
    )
    result = dispatch(
        IMAGE_IMPORT_OPERATIONS[0],
        json.dumps(request),
        {},
        services,
        FAILURE_CODES,
    )
    return result.model_dump(mode="json")


def import_inputs(
    tmp_path: Path, runtime: RuntimeObservation, *, indexed: bool = False
) -> tuple[Path, Path, Path]:
    """Write a source Sprite, a target with the same bytes and a 2 by 1 PNG.

    With indexed, the Sprite and the PNG are Indexed.
    """
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    import_target(runtime, source, **({"mode": "indexed"} if indexed else {}))
    target.write_bytes(source.read_bytes())
    if indexed:
        indexed_png(raster, [1, 1])
    else:
        Image.new("RGBA", (2, 1), (17, 31, 53, 128)).save(raster)
    return source, raster, target


def assert_unpublished(
    source: Path,
    raster: Path,
    target: Path,
    original: tuple[bytes, bytes, bytes],
    files: ObservedTargetFiles,
) -> None:
    """Check that the inputs keep their bytes, and that the one stage was discarded."""
    assert (source.read_bytes(), raster.read_bytes(), target.read_bytes()) == original
    assert len(files.stages) == 1
    assert files.discards == files.stages
    assert all(not stage.exists() for stage in files.stages)
    assert not list(target.parent.glob(".*.staged.aseprite"))
