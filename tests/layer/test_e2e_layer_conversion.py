"""Explicit Background Layer conversion through the installed CLI."""

import hashlib
import struct
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, render_frame, run, run_lua
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"
INELIGIBLE_SOURCE = (
    "Background conversion requires a visible, editable regular Transparent Image Layer"
)
EXISTING_BACKGROUND = "Sprite already has a Background Layer"
INCOMPATIBLE_FILL = (
    "background_color is incompatible with Sprite Color Mode or an Effective Palette "
    "at a Frame"
)
INELIGIBLE_BACKGROUND = (
    "Transparent conversion requires a visible, editable Background Layer"
)


def _assert_native_fill(runtime: RuntimeObservation, source: Path, mode: str) -> None:
    """Check the Background fill of source in mode with `assert_conversion_fill.lua`.

    The fixture exits with an error when a check fails.
    """
    lua = run_lua(
        FIXTURES / "assert_conversion_fill.lua", runtime, source=source, mode=mode
    )
    assert lua.returncode == 0, process_diagnostics(lua)


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
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "background.aseprite"
    lua = run_lua(FIXTURES / "conversion_rgb.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "layer convert-to-background",
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
    rendered = render_frame(target, 1)
    assert rendered.getpixel((3, 3)) == (10, 20, 30, 255)
    assert rendered.getpixel((0, 1))[3] == 255
    assert rendered.getpixel((0, 1)) != (10, 20, 30, 255)
    assert render_frame(target, 2).getpixel((0, 1)) == (
        10,
        20,
        30,
        255,
    )
    assert target.is_file()


def test_convert_background_to_transparent_preserves_cels_and_reports_native_name(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    background = tmp_path / "background.aseprite"
    transparent = tmp_path / "transparent.aseprite"
    lua = run_lua(FIXTURES / "conversion_rgb.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "layer convert-to-background",
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
    result = expect_success(
        "layer convert-from-background",
        {
            "source_sprite_file": str(background),
            "target_sprite_file": str(transparent),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1]},
        },
    )
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
    runtime: RuntimeObservation, tmp_path: Path, mode: str, color: dict
) -> None:
    source = tmp_path / f"{mode}.aseprite"
    target = tmp_path / "background.aseprite"
    lua = run_lua(FIXTURES / "conversion_modes.lua", runtime, out=source, mode=mode)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "layer convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_name": "subject"},
            "background_color": color,
        },
    )
    assert result["created_cels"] == 1
    assert result["after_layer"]["is_background"] is True
    _assert_native_fill(runtime, target, mode)
    transparent = tmp_path / "transparent.aseprite"
    reversed_result = expect_success(
        "layer convert-from-background",
        {
            "source_sprite_file": str(target),
            "target_sprite_file": str(transparent),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1]},
        },
    )
    assert reversed_result["after_layer"]["is_transparent"] is True
    assert reversed_result["after_layer"]["name"] == "Layer 0"
    assert reversed_result["before"]["cels"] == reversed_result["after"]["cels"]
    assert reversed_result["created_cels"] == 0


def test_nested_source_moves_to_root_bottom_and_reports_changed_addresses(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "background.aseprite"
    lua = run_lua(FIXTURES / "mutations.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    result = expect_success(
        "layer convert-to-background",
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
    assert result["before_layer"]["path"] == [3, 1]
    assert result["after_layer"]["path"] == [1]
    assert result["created_cels"] == 1
    assert result["affected_before"] == {
        "layer_paths": [[1], [2], [3], [3, 1]],
        "cels": [
            {"layer_path": [1], "frame_number": 1},
            {"layer_path": [2], "frame_number": 1},
            {"layer_path": [2], "frame_number": 2},
            {"layer_path": [3, 1], "frame_number": 1},
        ],
    }
    assert result["affected_after"] == {
        "layer_paths": [[1], [2], [3], [4]],
        "cels": [
            {"layer_path": [1], "frame_number": 1},
            {"layer_path": [1], "frame_number": 2},
            {"layer_path": [2], "frame_number": 1},
            {"layer_path": [3], "frame_number": 1},
            {"layer_path": [3], "frame_number": 2},
        ],
    }


@pytest.mark.parametrize(
    "variant", ["hidden", "locked", "hidden-parent", "group", "reference"]
)
def test_ineligible_source_fails_without_publishing_or_mutating_source(
    runtime: RuntimeObservation, tmp_path: Path, variant: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    lua = run_lua(
        FIXTURES / "conversion_ineligible.lua", runtime, out=source, mode=variant
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    outcome = run(
        "layer convert-to-background",
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
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert result["message"] == INELIGIBLE_SOURCE
    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ([1], INELIGIBLE_SOURCE),
        ([2], INELIGIBLE_SOURCE),
        ([2, 1], INELIGIBLE_SOURCE),
        ([2, 2], EXISTING_BACKGROUND),
    ],
    ids=["background", "group", "tilemap", "regular"],
)
def test_existing_background_or_unsupported_kind_blocks_forward_conversion(
    runtime: RuntimeObservation, tmp_path: Path, path: list[int], message: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    lua = run_lua(FIXTURES / "tilemap_subtree.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    outcome = run(
        "layer convert-to-background",
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
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert result["message"] == message
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
    runtime: RuntimeObservation,
    tmp_path: Path,
    mode: str,
    color: dict,
    expected_code: str,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    if mode == "rgb":
        lua = run_lua(FIXTURES / "conversion_rgb.lua", runtime, out=source)
    else:
        lua = run_lua(FIXTURES / "conversion_modes.lua", runtime, out=source, mode=mode)
    assert lua.returncode == 0, process_diagnostics(lua)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    outcome = run(
        "layer convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_name": "subject"},
            "background_color": color,
        },
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == expected_code
    assert result["message"] == INCOMPATIBLE_FILL
    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


@pytest.mark.parametrize("variant", ["hidden", "locked"])
def test_ineligible_background_fails_without_mutating_source(
    runtime: RuntimeObservation, tmp_path: Path, variant: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    lua = run_lua(
        FIXTURES / "conversion_background_ineligible.lua",
        runtime,
        out=source,
        mode=variant,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    outcome = run(
        "layer convert-from-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1]},
        },
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert result["message"] == INELIGIBLE_BACKGROUND
    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


def test_indexed_fill_must_be_opaque_in_every_frame_palette(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    lua = run_lua(
        FIXTURES / "conversion_modes.lua", runtime, out=source, mode="indexed"
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    _make_second_frame_fill_index_transparent(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    outcome = run(
        "layer convert-to-background",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "target": {"layer_name": "subject"},
            "background_color": {"kind": "palette-index", "index": 2},
        },
    )
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert result["message"] == INCOMPATIBLE_FILL
    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha


def test_invalid_in_place_conversion_does_not_change_source(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    lua = run_lua(FIXTURES / "conversion_rgb.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    outcome = run(
        "layer convert-to-background",
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
    result = outcome.envelope
    assert outcome.returncode == 2, result
    assert result["code"] == "layer_unsupported_target"
    assert result["message"] == INCOMPATIBLE_FILL
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
