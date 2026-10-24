"""Native representation admission and selection at the public animation boundary."""

from pathlib import Path

import pytest
from PIL import Image

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run
from tests.support import snapshot_fixture, source_sprite

pytestmark = pytest.mark.e2e


def _request(source: Path, directory: Path, operation: str = "sequence") -> dict:
    """Return an Export Sequence or Export GIF request of Frame 1.

    The request composes the visible Layers. A sequence writes
    `frame_{frame01}.png` in directory; a GIF writes `animation.gif` there.
    """
    destination = (
        {
            "directory": str(directory),
            "filename_format": "frame_{frame01}.png",
            "if_exists": "fail",
        }
        if operation == "sequence"
        else {"path": str(directory / "animation.gif"), "if_exists": "fail"}
    )
    return {
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": [1]},
        "layer_composition": {"mode": "visible"},
        "destination": destination,
    }


@pytest.mark.parametrize("operation", ["gif", "sequence"])
@pytest.mark.parametrize("mode", ["tilemap", "composition", "reference"])
def test_animation_reuses_native_tilemap_group_and_reference_selection(
    tmp_path: Path, runtime: RuntimeObservation, operation: str, mode: str
):
    source = snapshot_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    request = _request(source, tmp_path, operation)
    if mode == "composition":
        request["layer_composition"] = {
            "mode": "include",
            "layers": [{"layer_name": "Character"}],
        }
    result = expect_success(f"export {operation}", request)
    with Image.open(result["artifacts"][0]["path"]) as image:
        rgba = image.convert("RGBA")
        if mode == "tilemap":
            assert rgba.getpixel((1, 1)) == (250, 0, 0, 255)
        elif mode == "composition":
            assert rgba.getpixel((1, 1)) == (
                255,
                0,
                0,
                255 if operation == "gif" else 64,
            )
            assert rgba.getpixel((2, 1)) == (
                0,
                255,
                0,
                255 if operation == "gif" else 128,
            )
        else:
            assert max(rgba.tobytes()[3::4]) == 0
    if mode == "reference":
        request["destination"]["if_exists"] = "replace"
        request["layer_composition"] = {
            "mode": "include",
            "layers": [{"layer_path": [1]}],
        }
        outcome = run(f"export {operation}", request)
        result = outcome.envelope
        assert (
            outcome.returncode == 2 and result["code"] == "animation_export_invalid"
        ), result
        assert result["details"]["reason"] == "layer_composition"
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "mode,profile",
    [
        ("grayscale", "none"),
        ("indexed", "srgb"),
        ("rgb", "linear_srgb"),
        ("indexed", "display_p3_cc0"),
    ],
)
def test_gif_profile_matrix_gates_actual_native_conversion(
    tmp_path: Path, runtime: RuntimeObservation, mode: str, profile: str
):
    options = {"profile": profile}
    if profile in ("linear_srgb", "display_p3_cc0"):
        options["icc_file"] = str(
            (Path("src/spa/kernel/color/profiles") / f"{profile}.icc").resolve()
        )
    source = source_sprite(
        runtime, tmp_path, "animation_representation.lua", mode=mode, **options
    )
    request = _request(source, tmp_path, "gif")
    request["playback"]["frame_numbers"] = [2, 1]
    outcome = run("export gif", request)
    result = outcome.envelope
    converted = profile in ("linear_srgb", "display_p3_cc0")
    if (
        converted
        and "aseprite_convert_color_profile" not in runtime.verified_capabilities
    ):
        assert outcome.returncode != 0 and result["code"] == "runtime_incompatible", (
            result
        )
        assert not (tmp_path / "animation.gif").exists()
        return
    assert outcome.returncode == 0, result
    assert result["color_profile"] == {
        "source": "icc" if converted else profile,
        "source_icc_identity": profile if converted else None,
        "native_conversion": "to_srgb" if converted else "none",
        "encoded": "unprofiled",
    }


@pytest.mark.parametrize(
    "bad_format",
    [
        "frame.png",
        "{frame}.png",
        "{frame0}_{frame1}.png",
        "../{frame0}.png",
        "{tag}_{frame0}.png",
        "{frame2}.png",
        "{frame0}.gif",
    ],
)
def test_sequence_rejects_unsupported_names_without_final_output(
    tmp_path: Path, runtime: RuntimeObservation, bad_format: str
):
    source = source_sprite(runtime, tmp_path)
    request = _request(source, tmp_path)
    request["destination"]["filename_format"] = bad_format
    outcome = run("export sequence", request)
    result = outcome.envelope
    assert outcome.returncode == 2 and result["code"] == "animation_export_invalid", (
        result
    )
    assert result["details"]["reason"] == "filename_format"
    assert {p.name for p in tmp_path.iterdir()} == {"source.aseprite"}


def test_sequence_rejects_rgb_icc_on_grayscale_without_discarding_profile(
    tmp_path: Path,
    runtime: RuntimeObservation,
):
    profile = Path("src/spa/kernel/color/profiles/linear_srgb.icc").resolve()
    source = source_sprite(
        runtime,
        tmp_path,
        "animation_representation.lua",
        mode="grayscale",
        icc_file=str(profile),
    )
    outcome = run("export sequence", _request(source, tmp_path))
    result = outcome.envelope
    assert outcome.returncode == 2 and result["code"] == "animation_export_invalid", (
        result
    )
    assert result["details"]["reason"] == "color_profile"
    assert {p.name for p in tmp_path.iterdir()} == {"source.aseprite"}
