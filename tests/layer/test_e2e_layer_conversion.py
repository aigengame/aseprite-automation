"""Explicit Background Layer conversion through the installed CLI."""

import hashlib
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.aseprite.invocation import prepare_invocation
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e


def _fixture(target: Path, name: str, mode: str | None = None) -> None:
    aseprite = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    resource = aseprite.parent.parent / "Resources" / "data" / "gui.xml"
    script = Path(__file__).parent / "fixtures" / name
    with tempfile.TemporaryDirectory(prefix="spa-layer-conversion-fixture-") as work:
        prepared = prepare_invocation(aseprite, resource, Path(work))
        params = ["--script-param", f"mode={mode}"] if mode is not None else []
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={target}",
                *params,
                "--script",
                str(script),
            ],
            text=True,
            capture_output=True,
            env=prepared.environment,
            check=False,
        )
    assert run.returncode == 0, process_diagnostics(run)


def _run(command: str, request: dict[str, object]) -> tuple[int, dict]:
    run = spa(
        "layer",
        command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    return run.returncode, json.loads(run.stdout)


def _export(sprite_file: Path, frame_number: int, target: Path) -> Image.Image:
    run = spa(
        "export",
        "image",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(sprite_file),
                "destination": {"path": str(target), "if_exists": "fail"},
                "frame_number": frame_number,
                "export_image_area": {"kind": "canvas"},
                "layer_composition": {"mode": "visible"},
                "composition_color_mode": "preserve",
                "color_mode": "preserve",
                "color_profile": "preserve",
                "transparency": "preserve",
            }
        ),
    )
    assert run.returncode == 0, run.stdout
    with Image.open(target) as image:
        image.load()
        return image.convert("RGBA")


def _assert_native_fill(source: Path, mode: str) -> None:
    aseprite = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    resource = aseprite.parent.parent / "Resources" / "data" / "gui.xml"
    script = Path(__file__).parent / "fixtures" / "assert_conversion_fill.lua"
    with tempfile.TemporaryDirectory(prefix="spa-conversion-assert-") as work:
        prepared = prepare_invocation(aseprite, resource, Path(work))
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"source={source}",
                "--script-param",
                f"mode={mode}",
                "--script",
                str(script),
            ],
            text=True,
            capture_output=True,
            env=prepared.environment,
            check=False,
        )
    assert run.returncode == 0, process_diagnostics(run)


def _make_second_frame_fill_index_transparent(source: Path) -> None:
    """Write a frame-local Palette Chunk; the Lua API cannot author one."""
    payload = bytearray(source.read_bytes())
    frame_offset = 128 + struct.unpack_from("<I", payload, 128)[0]
    entries = b"".join(
        struct.pack("<HBBBB", 0, *rgba)
        for rgba in ((0, 0, 0, 0), (241, 82, 65, 255), (20, 40, 200, 0))
    )
    chunk_data = struct.pack("<III8x", 3, 0, 2) + entries
    chunk = struct.pack("<IH", len(chunk_data) + 6, 0x2019) + chunk_data
    frame_size = struct.unpack_from("<I", payload, frame_offset)[0]
    chunk_count = struct.unpack_from("<H", payload, frame_offset + 6)[0]
    extended_count = struct.unpack_from("<I", payload, frame_offset + 12)[0]
    struct.pack_into("<I", payload, frame_offset, frame_size + len(chunk))
    if extended_count:
        struct.pack_into("<I", payload, frame_offset + 12, extended_count + 1)
    else:
        struct.pack_into("<H", payload, frame_offset + 6, chunk_count + 1)
    payload[frame_offset + 16 : frame_offset + 16] = chunk
    struct.pack_into("<I", payload, 0, len(payload))
    source.write_bytes(payload)


def test_convert_transparent_layer_to_background_persists_full_canvas_cels(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "background.aseprite"
    _fixture(source, "conversion_rgb.lua")
    code, result = _run(
        "convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_name": "subject"},
            "background_color": {
                "kind": "rgba",
                "red": 10,
                "green": 20,
                "blue": 30,
                "alpha": 255,
            },
        },
    )
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    assert result["before_layer"]["name"] == "subject"
    assert result["after_layer"]["is_background"] is True
    assert result["after_layer"]["name"] == "Background"
    assert result["before_layer"]["opacity"] == 128
    assert result["after_layer"]["opacity"] == 255
    assert result["created_cels"] == 1
    assert result["affected_frame_numbers"] == [1, 2]
    assert result["cel_changes"][0]["before"]["bounds"] == {
        "x": -1,
        "y": 1,
        "width": 2,
        "height": 2,
    }
    assert result["cel_changes"][0]["before"]["opacity"] == 128
    assert result["cel_changes"][0]["after"]["bounds"] == {
        "x": 0,
        "y": 0,
        "width": 4,
        "height": 4,
    }
    assert result["cel_changes"][0]["after"]["opacity"] == 255
    cels = [
        cel
        for cel in result["after"]["cels"]
        if cel["layer_path"] == result["after_layer"]["path"]
    ]
    assert [cel["frame_number"] for cel in cels] == [1, 2]
    assert all(
        cel["bounds"] == {"x": 0, "y": 0, "width": 4, "height": 4} for cel in cels
    )
    assert all(cel["opacity"] == 255 for cel in cels)
    rendered = _export(target, 1, tmp_path / "frame-1.png")
    assert rendered.getpixel((3, 3)) == (10, 20, 30, 255)
    assert rendered.getpixel((0, 1))[3] == 255
    assert rendered.getpixel((0, 1)) != (10, 20, 30, 255)
    assert _export(target, 2, tmp_path / "frame-2.png").getpixel((0, 1)) == (
        10,
        20,
        30,
        255,
    )
    assert target.is_file()


def test_convert_background_to_transparent_preserves_cels_and_reports_native_name(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    background = tmp_path / "background.aseprite"
    transparent = tmp_path / "transparent.aseprite"
    _fixture(source, "conversion_rgb.lua")
    code, result = _run(
        "convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(background),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_name": "subject"},
            "background_color": {
                "kind": "rgba",
                "red": 10,
                "green": 20,
                "blue": 30,
                "alpha": 255,
            },
        },
    )
    assert code == 0, result
    code, result = _run(
        "convert-from-background",
        {
            "source_sprite_file": str(background),
            "target_sprite_file": str(transparent),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1]},
        },
    )
    assert code == 0, result
    assert result["before_layer"]["is_background"] is True
    assert result["after_layer"]["is_transparent"] is True
    assert result["after_layer"]["name"] == "Layer 0"
    assert result["created_cels"] == 0
    assert result["affected_frame_numbers"] == [1, 2]
    assert result["before"]["cels"] == result["after"]["cels"]
    assert all(
        frame["before_digest"] == frame["after_digest"]
        for frame in result["rendered_frames"]
    )
    assert transparent.is_file()


@pytest.mark.parametrize(
    ("mode", "color"),
    [
        ("grayscale", {"kind": "grayscale", "gray": 60, "alpha": 255}),
        ("indexed", {"kind": "palette-index", "index": 2}),
    ],
)
def test_convert_to_background_uses_compatible_color_in_each_mode(
    tmp_path: Path, mode: str, color: dict
) -> None:
    source = tmp_path / f"{mode}.aseprite"
    target = tmp_path / "background.aseprite"
    _fixture(source, "conversion_modes.lua", mode)
    code, result = _run(
        "convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_name": "subject"},
            "background_color": color,
        },
    )
    assert code == 0, result
    assert result["created_cels"] == 1
    assert result["after_layer"]["is_background"] is True
    _assert_native_fill(target, mode)
    transparent = tmp_path / "transparent.aseprite"
    code, reversed_result = _run(
        "convert-from-background",
        {
            "source_sprite_file": str(target),
            "target_sprite_file": str(transparent),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1]},
        },
    )
    assert code == 0, reversed_result
    assert reversed_result["after_layer"]["is_transparent"] is True
    assert reversed_result["after_layer"]["name"] == "Layer 0"
    assert reversed_result["before"]["cels"] == reversed_result["after"]["cels"]
    assert reversed_result["created_cels"] == 0


def test_nested_source_moves_to_root_bottom_and_reports_changed_addresses(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "background.aseprite"
    _fixture(source, "mutations.lua")
    code, result = _run(
        "convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [3, 1]},
            "background_color": {
                "kind": "rgba",
                "red": 10,
                "green": 20,
                "blue": 30,
                "alpha": 255,
            },
        },
    )
    assert code == 0, result
    assert result["before_layer"]["path"] == [3, 1]
    assert result["after_layer"]["path"] == [1]
    assert result["created_cels"] == 1
    assert [3, 1] in result["affected_before"]["layer_paths"]
    assert [1] in result["affected_after"]["layer_paths"]


@pytest.mark.parametrize(
    "variant", ["hidden", "locked", "hidden-parent", "group", "reference"]
)
def test_ineligible_source_fails_without_publishing_or_mutating_source(
    tmp_path: Path, variant: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source, "conversion_ineligible.lua", variant)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    code, result = _run(
        "convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_name": "subject"},
            "background_color": {
                "kind": "rgba",
                "red": 10,
                "green": 20,
                "blue": 30,
                "alpha": 255,
            },
        },
    )
    assert code == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


@pytest.mark.parametrize("path", [[1], [2], [2, 1], [2, 2]])
def test_existing_background_or_unsupported_kind_blocks_forward_conversion(
    tmp_path: Path, path: list[int]
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source, "tilemap_subtree.lua")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    code, result = _run(
        "convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": path},
            "background_color": {
                "kind": "rgba",
                "red": 10,
                "green": 20,
                "blue": 30,
                "alpha": 255,
            },
        },
    )
    assert code == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


@pytest.mark.parametrize(
    ("mode", "color", "expected_code"),
    [
        (
            "rgb",
            {"kind": "rgba", "red": 10, "green": 20, "blue": 30, "alpha": 128},
            "layer_unsupported_target",
        ),
        (
            "rgb",
            {"kind": "grayscale", "gray": 60, "alpha": 255},
            "layer_unsupported_target",
        ),
        (
            "grayscale",
            {"kind": "grayscale", "gray": 60, "alpha": 128},
            "layer_unsupported_target",
        ),
        ("indexed", {"kind": "palette-index", "index": 0}, "layer_unsupported_target"),
        ("indexed", {"kind": "palette-index", "index": 3}, "layer_unsupported_target"),
    ],
)
def test_incompatible_fill_rejects_before_publication(
    tmp_path: Path, mode: str, color: dict, expected_code: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(
        source,
        "conversion_rgb.lua" if mode == "rgb" else "conversion_modes.lua",
        None if mode == "rgb" else mode,
    )
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    code, result = _run(
        "convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_name": "subject"},
            "background_color": color,
        },
    )
    assert code == 2, result
    assert result["code"] == expected_code
    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


@pytest.mark.parametrize("variant", ["hidden", "locked"])
def test_ineligible_background_fails_without_mutating_source(
    tmp_path: Path, variant: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source, "conversion_background_ineligible.lua", variant)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    code, result = _run(
        "convert-from-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1]},
        },
    )
    assert code == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


def test_indexed_fill_must_be_opaque_in_every_frame_palette(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source, "conversion_modes.lua", "indexed")
    _make_second_frame_fill_index_transparent(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    code, result = _run(
        "convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_name": "subject"},
            "background_color": {"kind": "palette-index", "index": 2},
        },
    )
    assert code == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


def test_invalid_in_place_conversion_does_not_change_source(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, "conversion_rgb.lua")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    code, result = _run(
        "convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(source),
            "in_place": True,
            "overwrite": True,
            "target": {"layer_name": "subject"},
            "background_color": {
                "kind": "rgba",
                "red": 10,
                "green": 20,
                "blue": 30,
                "alpha": 0,
            },
        },
    )
    assert code == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
