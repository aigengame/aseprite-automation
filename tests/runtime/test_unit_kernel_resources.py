"""Packaged Kernel resources required by runtime capability probes."""

from importlib.resources import files


def test_probe_resources_are_packaged() -> None:
    kernel = files("spa.kernel")

    for name in (
        "sprite_create_support.lua",
        "sprite_inspection_fixture.aseprite",
        "paint_apply_support.lua",
        "sha256.lua",
    ):
        resource = kernel.joinpath(name)
        assert resource.is_file()
        assert len(resource.read_bytes()) > 0
