"""Packaged Kernel resources required by runtime capability probes."""

from importlib.resources import files


def test_probe_resources_are_packaged() -> None:
    kernel = files("spa.kernel")

    for name in (
        "sprite_create_support.lua",
        "sprite_inspection_fixture.aseprite",
        "paint_apply_support.lua",
        "paint_apply_fixture.aseprite",
        "digest.lua",
    ):
        resource = kernel.joinpath(name)
        assert resource.is_file()
        assert len(resource.read_bytes()) > 0


def test_paint_capability_probe_has_no_sprite_capability_gate() -> None:
    probe = files("spa.kernel").joinpath("probe.lua").read_text(encoding="utf-8")
    paint_probe = probe.split("local function observes_paint_apply()", 1)[1].split(
        "local function observed_capabilities()", 1
    )[0]

    assert "creation.execute" not in paint_probe
    assert "inspection" not in paint_probe
    assert "if observes_paint_apply() then" in probe
