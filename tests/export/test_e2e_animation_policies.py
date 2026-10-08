"""Native representation admission and selection at the public animation boundary."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.aseprite.aseprite import probe
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.export.test_e2e_export_image import _source
from tests.image.test_e2e_image_snapshot import _fixture as composition_fixture
from tests.support import spa

pytestmark = pytest.mark.e2e


def _request(source: Path, directory: Path, operation: str = "sequence") -> dict:
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
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": [1]},
        "layer_composition": {"mode": "visible"},
        "destination": destination,
    }


def _run(operation: str, request: dict) -> tuple[int, dict]:
    run = spa("export", operation, "--input-json", json.dumps(request))
    return run.returncode, json.loads(run.stdout)


@pytest.mark.parametrize("operation", ["gif", "sequence"])
@pytest.mark.parametrize("mode", ["tilemap", "composition", "reference"])
def test_animation_reuses_native_tilemap_group_and_reference_selection(
    tmp_path: Path, operation: str, mode: str
):
    source = composition_fixture(tmp_path, mode)
    original = source.read_bytes()
    request = _request(source, tmp_path, operation)
    if mode == "composition":
        request["layer_composition"] = {
            "mode": "include",
            "layers": [{"layer_name": "Character"}],
        }
    code, result = _run(operation, request)
    assert code == 0, result
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
        code, result = _run(operation, request)
        assert code == 2 and result["code"] == "animation_export_invalid", result
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
    tmp_path: Path, mode: str, profile: str
):
    options = {"profile": profile}
    if profile in ("linear_srgb", "display_p3_cc0"):
        options["icc_file"] = str(
            (Path("src/spa/kernel/color/profiles") / f"{profile}.icc").resolve()
        )
    source = _source(tmp_path, "animation_representation.lua", mode=mode, **options)
    request = _request(source, tmp_path, "gif")
    request["playback"]["frame_numbers"] = [2, 1]
    runtime = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    code, result = _run("gif", request)
    converted = profile in ("linear_srgb", "display_p3_cc0")
    if (
        converted
        and "aseprite_convert_color_profile" not in runtime.verified_capabilities
    ):
        assert code != 0 and result["code"] == "runtime_incompatible", result
        assert not (tmp_path / "animation.gif").exists()
        return
    assert code == 0, result
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
    tmp_path: Path, bad_format: str
):
    source = _source(tmp_path)
    request = _request(source, tmp_path)
    request["destination"]["filename_format"] = bad_format
    code, result = _run("sequence", request)
    assert code == 2 and result["code"] == "animation_export_invalid", result
    assert {p.name for p in tmp_path.iterdir()} == {"source.aseprite"}


def test_sequence_rejects_rgb_icc_on_grayscale_without_discarding_profile(
    tmp_path: Path,
):
    profile = Path("src/spa/kernel/color/profiles/linear_srgb.icc").resolve()
    source = _source(
        tmp_path,
        "animation_representation.lua",
        mode="grayscale",
        icc_file=str(profile),
    )
    code, result = _run("sequence", _request(source, tmp_path))
    assert code == 2 and result["code"] == "animation_export_invalid", result
    assert {p.name for p in tmp_path.iterdir()} == {"source.aseprite"}
