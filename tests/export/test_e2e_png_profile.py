"""PNG profile preparation preserves native values without trusting backend names."""

from importlib.resources import files
from pathlib import Path

import pytest
from PIL import Image

from tests.export.support import png_icc_label, source_sprite

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("profile", ["none", "srgb", "linear_srgb", "display_p3"])
def test_png_profile_copy_preserves_content_and_input(tmp_path: Path, profile: str):
    kernel = files("spa.kernel")
    icc = kernel.joinpath(f"color/profiles/{profile}.icc")
    source_sprite(
        tmp_path,
        "png_profile.lua",
        profile=profile,
        icc_file=str(icc),
        directory=str(tmp_path),
        export_image_support=str(kernel.joinpath("delivery/export_image_support.lua")),
        color_profile_file=str(kernel.joinpath("color/profile_file.lua")),
    )
    is_icc = profile in ("linear_srgb", "display_p3")
    outputs = sorted(tmp_path.glob("profile-*.png"))
    assert len(outputs) == (4 if is_icc else 1)
    for path in outputs:
        with Image.open(path) as image:
            assert image.convert("RGBA").getpixel((0, 0)) == (31, 63, 127, 128)
            if is_icc:
                assert image.info["icc_profile"] == icc.read_bytes()
                assert png_icc_label(path.read_bytes()) == profile.encode("ascii")
            else:
                assert "icc_profile" not in image.info
                assert image.info.get("srgb") == (0 if profile == "srgb" else None)
