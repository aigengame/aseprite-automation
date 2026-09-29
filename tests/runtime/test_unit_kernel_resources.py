"""Packaged Kernel resources required by runtime capability probes."""

from importlib.resources import files


def test_probe_resources_are_packaged() -> None:
    kernel = files("spa.kernel")

    for name in (
        "sprite_create_support.lua",
        "sprite_inspection_fixture.aseprite",
        "paint_apply_support.lua",
        "native_tool.lua",
        "paint_native_support.lua",
        "paint_fill.lua",
        "paint_pencil.lua",
        "paint_eraser.lua",
        "paint_line.lua",
        "paint_rectangle.lua",
        "paint_ellipse.lua",
        "paint_apply_fixture.aseprite",
        "capability_probe.lua",
        "digest.lua",
        "selection_mask.lua",
        "selection_support.lua",
        "selection_create.lua",
        "selection_combine.lua",
        "selection_invert.lua",
        "selection_grow.lua",
        "selection_shrink.lua",
        "selection_transform.lua",
        "selection_export.lua",
        "selection_preview.lua",
        "image_resize.lua",
        "image_resize_transform.lua",
        "effective_palette.lua",
        "image_orientation.lua",
        "image_orientation_transform.lua",
    ):
        resource = kernel.joinpath(name)
        assert resource.is_file()
        assert len(resource.read_bytes()) > 0


def test_paint_capability_probe_has_no_sprite_capability_gate() -> None:
    probe = (
        files("spa.kernel").joinpath("capability_probe.lua").read_text(encoding="utf-8")
    )
    paint_probe = probe.split("local function observes_paint_apply()", 1)[1].split(
        "function module.observe()", 1
    )[0]

    assert "creation.execute" not in paint_probe
    assert "inspection" not in paint_probe
    assert "if observes_paint_apply() then" in probe
