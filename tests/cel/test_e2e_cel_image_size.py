"""Bounded real-native matrix: stored pixels, geometry, links, and document facts."""

from pathlib import Path

import pytest
from PIL import ImageCms

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run_lua
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


def _image_size(runtime: RuntimeObservation, **params: object) -> None:
    """Run `image_size.lua`, which writes the source Sprite or checks an added Cel.

    The fixture can print a Lua error, so the output must not contain "Error".
    """
    lua = run_lua(
        Path(__file__).parent / "fixtures" / "image_size.lua", runtime, **params
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    assert "Error" not in lua.stdout + lua.stderr, process_diagnostics(lua)


def _add(source: Path, target: Path, size: dict, *, plan: bool) -> dict:
    """Add a Cel at [1]@3 with size, as a standalone command or a one-step Plan.

    Check the Target Commit and the reopen verification, and return the Cel facts.
    """
    cel_input = {"target": {"layer": {"layer_path": [1]}, "frame_number": 3}, **size}
    files = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
    }
    if plan:
        result = expect_success(
            "plan run",
            {
                "plan": {
                    **files,
                    "steps": [{"operation": "cel add", "input": cel_input}],
                }
            },
        )
    else:
        result = expect_success("cel add", {**files, **cel_input})
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
    runtime: RuntimeObservation, tmp_path: Path, size: dict, mode: str, plan: bool
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "added.aseprite"
    _image_size(runtime, mode=mode, out=source)
    before = source.read_bytes()
    cel = _add(source, target, size, plan=plan)
    dimensions = size.get("image_size") or {"width": 8, "height": 6}
    assert cel["image_bounds"] == {"x": 0, "y": 0, **dimensions}
    assert cel["linked_cels"] == []
    _image_size(runtime, source=source, result=target, **dimensions)
    assert source.read_bytes() == before


def test_add_inherits_embedded_color_profile(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    icc = tmp_path / "profile.icc"
    icc.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    source = tmp_path / "source.aseprite"
    target = tmp_path / "added.aseprite"
    _image_size(runtime, mode="rgb", out=source, icc=icc)
    size = {"width": 5, "height": 5}
    _add(source, target, {"image_size": size}, plan=False)
    _image_size(runtime, source=source, result=target, **size)
