"""Real Kernel admission and staged publication with selected-runtime capabilities."""

from dataclasses import replace
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import invoke
from spa.adapters.files import LocalTargetFiles
from spa.authoring.raster.filter import (
    FILTER_RESOURCES,
    BrightnessContrastRequest,
    brightness_contrast,
)
from spa.contracts.ports import OperationIssue, OperationServices
from tests.filter.support import native_script, observe_images, pixels

pytestmark = pytest.mark.e2e


def execute(runtime, source, target, application):
    observed = replace(
        runtime,
        verified_capabilities=tuple(
            capability
            for capability in runtime.verified_capabilities
            if capability != "aseprite_filter_brightness_contrast_tilemap_manual"
        ),
    )
    services = OperationServices(lambda _: observed, invoke, LocalTargetFiles())
    return brightness_contrast(
        BrightnessContrastRequest(
            source_sprite_file=str(source),
            target_sprite_file=str(target),
            in_place=False,
            overwrite=True,
            brightness=50,
            contrast=0,
            application=application,
        ),
        services,
    )


def test_missing_tile_capability_rejects_whole_mixed_request(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="rgb")
    original = source.read_bytes()
    target.write_bytes(b"prior target")
    with pytest.raises(OperationIssue) as caught:
        execute(
            runtime,
            source,
            target,
            pixels(tileset_mode="manual", cels_target={"kind": "all"}),
        )
    assert caught.value.code == "filter_unsupported_document"
    assert "capability" in caught.value.details.reason
    assert source.read_bytes() == original
    assert target.read_bytes() == b"prior target"


@pytest.mark.parametrize("palette_only", [False, True])
def test_missing_tile_capability_keeps_ordinary_and_palette_only_available(
    tmp_path, runtime, palette_only
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime,
        "tilemap.lua",
        source=source,
        mode="indexed",
        only=str(palette_only).lower(),
    )
    before = observe_images(runtime, source)
    application = (
        {
            "kind": "indexed-palette-entries",
            "palette_frame_number": 1,
            "entries": {"kind": "selected", "indexes": [1]},
            "channels": {"kind": "components", "names": ["red"]},
        }
        if palette_only
        else pixels("indexed", palette_frame_number=1, tileset_mode="manual")
    )
    result = execute(runtime, source, target, application)
    assert result.changed
    assert result.observed_tileset_mode is None
    assert result.changed_tiles == []
    assert observe_images(runtime, target)["tiles"] == before["tiles"]


def test_native_mode_mismatch_is_refused_without_mode_switch(tmp_path, runtime):
    kernel = Path(__file__).resolve().parents[2] / "src" / "spa" / "kernel"
    native_script(
        runtime,
        "tilemap_admission.lua",
        **{
            resource.parameter_name: kernel / resource.package_path
            for resource in FILTER_RESOURCES
        },
    )
