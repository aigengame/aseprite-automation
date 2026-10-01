"""Packaged Kernel resources required by runtime capability probes."""

from importlib.resources import files

import pytest

from spa.contracts.ports import PackagedHandler, PackagedResource


@pytest.mark.parametrize(
    "path",
    [
        "../probe.lua",
        "/probe.lua",
        "runtime/../probe.lua",
        "runtime//probe.lua",
        "runtime\\probe.lua",
        "runtime/./probe.lua",
        "runtime/probe.py",
    ],
)
def test_packaged_paths_remain_relative_fixed_resources(path: str) -> None:
    with pytest.raises(ValueError):
        PackagedResource("probe", path)
    with pytest.raises(ValueError):
        PackagedHandler("probe", path)


def test_resource_parameters_remain_independent_of_package_paths() -> None:
    resource = PackagedResource("inspection", "document/sprite/sprite_inspect.lua")
    handler = PackagedHandler(
        "sprite_get", "document/sprite/sprite_get.lua", (resource,)
    )
    assert handler.support_resources[0].parameter_name == "inspection"
    with pytest.raises(ValueError):
        PackagedHandler("document/sprite_get", handler.package_path)
    with pytest.raises(ValueError):
        PackagedHandler("sprite_get", handler.package_path, (resource, resource))


def test_probe_resources_are_packaged() -> None:
    kernel = files("spa.kernel")

    for name in (
        "document/sprite/sprite_create_support.lua",
        "runtime/fixtures/sprite_inspection_fixture.aseprite",
        "raster/paint/paint_apply_support.lua",
        "raster/paint/native_tool.lua",
        "raster/paint/paint_native_support.lua",
        "raster/paint/paint_fill.lua",
        "raster/paint/paint_pencil.lua",
        "raster/paint/paint_eraser.lua",
        "raster/paint/paint_line.lua",
        "raster/paint/paint_rectangle.lua",
        "raster/paint/paint_ellipse.lua",
        "raster/paint/paint_contour.lua",
        "raster/paint/paint_blur.lua",
        "runtime/fixtures/paint_apply_fixture.aseprite",
        "runtime/capability_probe.lua",
        "foundation/digest.lua",
        "raster/selection/selection_mask.lua",
        "raster/selection/selection_support.lua",
        "raster/selection/selection_create.lua",
        "raster/selection/selection_combine.lua",
        "raster/selection/selection_invert.lua",
        "raster/selection/selection_grow.lua",
        "raster/selection/selection_shrink.lua",
        "raster/selection/selection_transform.lua",
        "raster/selection/selection_export.lua",
        "raster/selection/selection_preview.lua",
        "raster/image/image_resize.lua",
        "raster/image/image_resize_transform.lua",
        "color/effective_palette.lua",
        "color/palette_support.lua",
        "color/palette_read.lua",
        "color/palette_set.lua",
        "color/palette_transform.lua",
        "color/palette_transform_run.lua",
        "color/palette_images.lua",
        "color/palette_file.lua",
        "color/palette_quantization.lua",
        "delivery/palette_export.lua",
        "color/profile.lua",
        "color/profile_file.lua",
        "color/profile_mutation.lua",
        "color/profiles/linear_srgb.icc",
        "color/profiles/display_p3.icc",
        "raster/image/image_orientation.lua",
        "raster/image/image_orientation_transform.lua",
    ):
        resource = kernel.joinpath(name)
        assert resource.is_file()
        assert len(resource.read_bytes()) > 0


def test_paint_capability_probe_has_no_sprite_capability_gate() -> None:
    probe = (
        files("spa.kernel")
        .joinpath("runtime/capability_probe.lua")
        .read_text(encoding="utf-8")
    )
    paint_probe = probe.split("local function observes_paint_apply()", 1)[1].split(
        "function module.observe()", 1
    )[0]

    assert "creation.execute" not in paint_probe
    assert "inspection" not in paint_probe
    assert "if observes_paint_apply() then" in probe
