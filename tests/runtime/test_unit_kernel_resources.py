"""Packaged Kernel resources required by runtime capability probes."""

from importlib.resources import files


def test_sprite_inspection_probe_fixture_is_packaged() -> None:
    fixture = files("spa.kernel").joinpath("sprite_inspection_fixture.aseprite")

    assert fixture.is_file()
    assert len(fixture.read_bytes()) > 0
