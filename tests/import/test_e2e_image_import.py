"""Compatible raster insertion through the installed CLI and real Aseprite."""

import hashlib
import json
import os
import subprocess
import tempfile
from importlib.resources import files
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import (
    icc_fixture_path,
    inject_palette_change,
    process_diagnostics,
    spa,
)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


def _create(runtime, source: Path, **params: str) -> None:
    with tempfile.TemporaryDirectory(prefix="spa-import-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        arguments = [str(prepared.executable), "--batch"]
        for key, value in {"out": str(source), **params}.items():
            arguments.extend(["--script-param", f"{key}={value}"])
        run = subprocess.run(
            [
                *arguments,
                "--script",
                str(Path(__file__).parent / "fixtures/import_target.lua"),
            ],
            env=prepared.environment,
            text=True,
            capture_output=True,
            check=False,
        )
    assert run.returncode == 0, process_diagnostics(run)


def _import(source: Path, raster: Path, target_file: Path, **extra):
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(target_file),
        "in_place": source == target_file,
        "overwrite": True,
        "raster_file": str(raster),
        "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
        "position": {"x": -1, "y": 1},
        **extra,
    }
    run = spa("image", "import", "--input-json", json.dumps(request))
    assert run.stdout, process_diagnostics(run)
    return run.returncode, json.loads(run.stdout)


def test_import_rgba_preserves_complete_pixels_and_off_canvas_placement(
    tmp_path, runtime
):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    _create(runtime, source)
    pixels = bytes([10, 20, 30, 255, 60, 70, 80, 128, 90, 100, 110, 0, 0, 0, 0, 0])
    Image.frombytes("RGBA", (4, 1), pixels).save(raster)
    original, png = source.read_bytes(), raster.read_bytes()
    code, result = _import(source, raster, target)
    assert code == 0, json.dumps(result, indent=2)
    assert result["persisted_reopen_verified"] is True
    assert result["cel"]["frame_number"] == 2
    assert result["cel"]["layer_path"] == [1]
    assert result["cel"]["image_bounds"] == {"x": -1, "y": 1, "width": 4, "height": 1}
    assert result["cel"]["opacity"] == 255
    assert result["cel"]["z_index"] == 0
    assert result["cel"]["linked_cels"] == []
    assert result["raster_file"]["sha256"] == hashlib.sha256(png).hexdigest()
    assert result["image"]["stored_content_digest"] == {
        "algorithm": "fnv1a64",
        "value": "2d20e989cbe59ace",
    }
    assert (
        result["image"]["rgba_content_digest"]
        == result["image"]["stored_content_digest"]
    )
    assert source.read_bytes() == original
    assert raster.read_bytes() == png
    read = spa(
        "image",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(target),
                "source": {
                    "kind": "individual",
                    "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
                    "rectangle": {"x": 0, "y": 0, "width": 4, "height": 1},
                },
            }
        ),
    )
    assert read.returncode == 0, read.stdout
    colors = [run["color"] for run in json.loads(read.stdout)["snapshot"]["rows"][0]]
    assert [(c["red"], c["green"], c["blue"], c["alpha"]) for c in colors] == list(
        zip(*[iter(pixels)] * 4)
    )


def _indexed(path, indexes, *, colors=None, alpha=b"\x00\xff\x80\xff"):
    entries = colors or [(0, 0, 0), (200, 20, 40), (10, 80, 160), (17, 31, 53)]
    image = Image.new("P", (len(indexes), 1))
    image.putpalette([component for entry in entries for component in entry])
    image.putdata(indexes)
    image.save(path, bits=8, transparency=alpha)


def test_import_indexed_matches_used_entries_only(tmp_path, runtime):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    _create(runtime, source, mode="indexed")
    _indexed(
        raster,
        [0, 1, 1],
        colors=[(0, 0, 0), (200, 20, 40), (9, 9, 9)],
        alpha=b"\x00\xff\xff",
    )
    original = source.read_bytes()
    code, result = _import(source, raster, target)
    assert code == 0, json.dumps(result, indent=2)
    assert result["image"]["color_mode"] == "indexed"
    assert result["effective_palette"]["palette_size"] == 4
    assert [item["index"] for item in result["effective_palette"]["indexes"]] == [0, 1]
    assert result["transparent_index"] == 0
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "profile_name", ["srgb", "linear_srgb", "display_p3_cc0", "display_p3"]
)
def test_import_same_encoded_profile_preserves_profile(tmp_path, runtime, profile_name):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    kwargs = {}
    if profile_name == "srgb":
        _create(runtime, source, profile="srgb")
        info = PngInfo()
        info.add(b"sRGB", b"\0")
        kwargs["pnginfo"] = info
    else:
        icc = icc_fixture_path(profile_name)
        _create(runtime, source, profile="icc", icc=str(icc))
        kwargs["icc_profile"] = icc.read_bytes()
    Image.new("RGB", (2, 2), (17, 31, 53)).save(raster, **kwargs)
    original = source.read_bytes()
    code, result = _import(source, raster, target)
    assert code == 0, json.dumps(result, indent=2)
    assert result["color_profile"] == {
        "kind": "srgb" if profile_name == "srgb" else "icc",
        "icc_identity": None if profile_name == "srgb" else profile_name,
    }
    assert result["raster_file"]["color_profile"] == result["color_profile"]
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "scenario", ["different_mask", "partial_alpha", "multiple_transparent"]
)
def test_compatible_indexed_transparency_uses_actual_index_meaning(
    tmp_path, runtime, scenario
):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    if scenario == "different_mask":
        _create(runtime, source, mode="indexed", mask="3")
        _indexed(raster, [1, 1], alpha=None)
    elif scenario == "partial_alpha":
        _create(runtime, source, mode="indexed")
        _indexed(raster, [2, 1])
    else:
        entries = [(0, 0, 0, 0), (0, 0, 0, 0), (10, 80, 160, 255)]
        _create(runtime, source, mode="indexed", palette=json.dumps(entries))
        _indexed(
            raster,
            [0, 1, 2],
            colors=[entry[:3] for entry in entries],
            alpha=bytes(entry[3] for entry in entries),
        )
    code, result = _import(source, raster, target)
    assert code == 0, json.dumps(result, indent=2)
    assert result["persisted_reopen_verified"] is True


@pytest.mark.parametrize(
    "scenario,reason",
    [
        ("changed_color", "palette"),
        ("undefined_destination_index", "palette"),
        ("opaque_mask", "palette"),
        ("transparent_hidden_rgb", "native_content"),
        ("partial_alpha_mask_loss", "native_content"),
    ],
)
def test_incompatible_indexed_pixels_never_publish(tmp_path, runtime, scenario, reason):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    _create(runtime, source, mode="indexed")
    if scenario == "changed_color":
        _indexed(raster, [1], colors=[(0, 0, 0), (201, 20, 40)])
    elif scenario == "undefined_destination_index":
        _indexed(raster, [4], colors=[(0, 0, 0)] * 5)
    elif scenario == "opaque_mask":
        _indexed(raster, [0], alpha=None)
    elif scenario == "transparent_hidden_rgb":
        _indexed(raster, [0], colors=[(99, 88, 77), (200, 20, 40)], alpha=b"\0\xff")
    else:
        _indexed(raster, [0, 1], alpha=b"\xff\x80\xff\xff")
    original, png = source.read_bytes(), raster.read_bytes()
    target.write_bytes(b"prior Target")
    code, result = _import(source, raster, target)
    assert code == 2, json.dumps(result, indent=2)
    assert result["code"] == "image_import_incompatible"
    assert result["details"]["reason"] == reason, result
    assert source.read_bytes() == original
    assert raster.read_bytes() == png
    assert target.read_bytes() == b"prior Target"
    assert not list(tmp_path.glob("*.staged.aseprite"))


def test_import_uses_selected_frame_effective_palette(tmp_path, runtime):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    _create(runtime, source, mode="indexed")
    entries = [(0, 0, 0, 0), (21, 43, 65, 255)]
    inject_palette_change(source, entries, frame_number=2)
    _indexed(raster, [1], colors=[entry[:3] for entry in entries], alpha=b"\0\xff")
    code, result = _import(source, raster, target)
    assert code == 0, json.dumps(result, indent=2)
    assert result["effective_palette"]["palette_frame_number"] == 2
    assert result["effective_palette"]["palette_size"] == 2
    code, result = _import(
        source,
        raster,
        tmp_path / "wrong.aseprite",
        target={"layer": {"layer_path": [1]}, "frame_number": 1},
    )
    assert code == 2, result
    assert result["details"]["reason"] == "palette"
    assert not (tmp_path / "wrong.aseprite").exists()


@pytest.mark.parametrize(
    "scenario,expected_code",
    [
        ("occupied", "cel_already_exists"),
        ("linked", "cel_already_exists"),
        ("group", "cel_unsupported_target"),
        ("reference", "cel_unsupported_target"),
        ("background", "cel_unsupported_target"),
        ("missing_layer", "layer_invalid_path"),
        ("missing_frame", "cel_frame_out_of_bounds"),
        ("grayscale", "image_import_incompatible"),
        ("indexed", "image_import_incompatible"),
    ],
)
def test_target_refusals_preserve_existing_files(
    tmp_path, runtime, scenario, expected_code
):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    params = (
        {scenario: "yes"}
        if scenario in ("occupied", "linked")
        else {"target_kind": scenario}
    )
    if scenario in ("grayscale", "indexed"):
        params = {"mode": scenario}
    _create(runtime, source, **params)
    Image.new("RGBA", (1, 1), (10, 20, 30, 255)).save(raster)
    original = source.read_bytes()
    target.write_bytes(b"prior Target")
    extra = {}
    if scenario in ("missing_layer", "missing_frame"):
        extra = {
            "target": {
                "layer": {"layer_path": [99 if scenario == "missing_layer" else 1]},
                "frame_number": 99 if scenario == "missing_frame" else 2,
            }
        }
    code, result = _import(source, raster, target, **extra)
    assert code == 2, json.dumps(result, indent=2)
    assert result["code"] == expected_code
    assert source.read_bytes() == original
    assert target.read_bytes() == b"prior Target"


@pytest.mark.parametrize(
    "source_profile,png_profile",
    [
        ("srgb", "none"),
        ("none", "srgb"),
        ("srgb", "linear_srgb"),
        ("linear_srgb", "display_p3_cc0"),
    ],
)
def test_profile_mismatch_is_not_converted(
    tmp_path, runtime, source_profile, png_profile
):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    params = {"profile": source_profile}
    if source_profile not in ("none", "srgb"):
        params = {
            "profile": "icc",
            "icc": str(
                files("spa.kernel").joinpath(f"color/profiles/{source_profile}.icc")
            ),
        }
    _create(runtime, source, **params)
    kwargs = {}
    if png_profile == "srgb":
        info = PngInfo()
        info.add(b"sRGB", b"\0")
        kwargs["pnginfo"] = info
    elif png_profile != "none":
        kwargs["icc_profile"] = (
            files("spa.kernel")
            .joinpath(f"color/profiles/{png_profile}.icc")
            .read_bytes()
        )
    Image.new("RGBA", (1, 1), (10, 20, 30, 128)).save(raster, **kwargs)
    original = source.read_bytes()
    code, result = _import(source, raster, target)
    assert code == 2, result
    assert result["details"]["reason"] == "color_profile"
    assert source.read_bytes() == original
    assert not target.exists()


def test_import_is_independent_and_preserves_existing_links_in_place(tmp_path, runtime):
    source, raster = tmp_path / "source.aseprite", tmp_path / "input.png"
    _create(runtime, source, linked="yes")
    Image.new("RGBA", (1, 1), (12, 34, 56, 255)).save(raster)
    original_png = raster.read_bytes()
    code, result = _import(
        source,
        raster,
        source,
        target={"layer": {"layer_name": "Destination"}, "frame_number": 3},
        position={"x": 32767, "y": -32768},
    )
    assert code == 0, json.dumps(result, indent=2)
    assert result["cel"]["linked_cels"] == []
    assert result["cel"]["image_bounds"] == {
        "x": 32767,
        "y": -32768,
        "width": 1,
        "height": 1,
    }
    existing = spa(
        "cel",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(source),
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            }
        ),
    )
    assert existing.returncode == 0, existing.stdout
    assert json.loads(existing.stdout)["cel"]["linked_cels"] == [
        {"layer_path": [1], "frame_number": 2}
    ]
    assert raster.read_bytes() == original_png


def test_rgb_transparent_color_keeps_hidden_rgb(tmp_path, runtime):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    _create(runtime, source)
    image = Image.new("RGB", (2, 1), (17, 31, 53))
    image.save(raster, transparency=(17, 31, 53))
    code, result = _import(source, raster, target)
    assert code == 0, json.dumps(result, indent=2)
    assert result["cel"]["content"] == "transparent"
    assert result["image"]["width"] == 2


def test_read_only_input_extension_is_not_used_as_format_evidence(tmp_path, runtime):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.bin", "target.aseprite")
    )
    _create(runtime, source)
    Image.new("RGBA", (2, 3), (0, 0, 0, 0)).save(raster, format="PNG")
    raster.chmod(0o444)
    code, result = _import(source, raster, target)
    assert code == 0, json.dumps(result, indent=2)
    assert result["cel"]["content"] == "transparent"
    assert result["raster_file"]["format"] == "png"
