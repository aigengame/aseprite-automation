"""Explicit static PNG area and composition through the installed public CLI."""

import hashlib
import json
import os
import struct
from pathlib import Path

import pytest
from PIL import Image

from tests.export.support import source_sprite
from tests.support import spa

pytestmark = pytest.mark.e2e


def _request(source: Path, destination: Path, **choices: object) -> dict:
    return {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "destination": {"path": str(destination), "if_exists": "fail"},
        "frame_number": 1,
        "export_image_area": {"kind": "canvas"},
        "layer_composition": {"mode": "visible"},
        "composition_color_mode": "preserve",
        "color_mode": "preserve",
        "color_profile": "preserve",
        "transparency": "preserve",
        **choices,
    }


def _export(request: dict) -> dict:
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    destination = Path(request["destination"]["path"])
    payload = destination.read_bytes()
    assert result["artifact"] == {
        "role": "image",
        "path": str(destination),
        "media_type": "image/png",
        "format": "png",
        "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    return result


def test_rectangle_rebases_source_canvas_pixels_to_output_origin(
    tmp_path: Path,
) -> None:
    source = source_sprite(tmp_path, "static_geometry.lua")
    before = source.read_bytes()
    destination = tmp_path / "crop.png"
    rectangle = {"x": 2, "y": 1, "width": 2, "height": 2}
    result = _export(
        _request(
            source,
            destination,
            frame_number=2,
            export_image_area={"kind": "rectangle", "rectangle": rectangle},
        )
    )
    assert result["export_image_area"]["rectangle"] == rectangle
    assert (result["width"], result["height"]) == (2, 2)
    with Image.open(destination) as image:
        assert image.mode == "RGBA" and image.size == (2, 2)
        assert list(image.get_flattened_data()) == [
            (50, 70, 100, 255),
            (70, 70, 100, 255),
            (50, 110, 100, 255),
            (70, 110, 100, 255),
        ]
    assert source.read_bytes() == before


def test_opaque_request_keeps_existing_indexed_background_mask_pixels(
    tmp_path: Path,
) -> None:
    source = source_sprite(
        tmp_path, "static_geometry.lua", variant="indexed_background"
    )
    before = source.read_bytes()
    destination = tmp_path / "opaque-background.png"
    result = _export(
        _request(
            source,
            destination,
            layer_composition={"mode": "include", "layers": [{"layer_path": [1]}]},
            transparency={
                "kind": "background",
                "background_color": {"kind": "palette-index", "index": 4},
            },
        )
    )
    assert result["effective_background"] is True
    assert result["alpha_channel"]["minimum"] == 255
    with Image.open(destination) as image:
        assert list(image.get_flattened_data()) == [1, 7, 7]
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (200, 0, 0, 255),
            (70, 77, 84, 255),
            (70, 77, 84, 255),
        ]
    assert source.read_bytes() == before


@pytest.mark.parametrize("partial_content", [False, True])
def test_existing_background_still_checks_color_and_encoded_opacity(
    tmp_path, partial_content
):
    source = source_sprite(
        tmp_path, "static_geometry.lua", variant="indexed_background"
    )
    before = source.read_bytes()
    destination = tmp_path / "existing-background.png"
    destination.write_bytes(b"keep destination")
    request = _request(
        source,
        destination,
        layer_composition=(
            {"mode": "visible"}
            if partial_content
            else {"mode": "include", "layers": [{"layer_path": [1]}]}
        ),
        transparency={
            "kind": "background",
            "background_color": {
                "kind": "palette-index",
                "index": 4 if partial_content else 2,
            },
        },
    )
    request["destination"]["if_exists"] = "replace"
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode != 0
    failure = json.loads(run.stdout)
    assert failure["code"] == "export_image_invalid"
    assert failure["details"]["reason"] == "background"
    assert (
        source.read_bytes() == before
        and destination.read_bytes() == b"keep destination"
    )
    assert not list(tmp_path.glob("*.staged.*"))


def _animated_slices(source: Path) -> None:
    # Fixture-only file-format injection supplies Keys absent from Lua setters.
    chunks = []
    for name, keys in [
        ("animated", [(0, 0, 0, 2, 1), (2, 2, 1, 2, 2)]),
        ("late", [(2, 0, 0, 1, 1)]),
        ("same", [(0, 0, 0, 1, 1)]),
        ("same", [(0, 1, 0, 1, 1)]),
        ("outside", [(0, 4, 2, 2, 1)]),
    ]:
        encoded = name.encode()
        body = struct.pack("<IIIH", len(keys), 0, 0, len(encoded)) + encoded
        for key in keys:
            body += struct.pack("<IiiII", *key)
        chunks.append(struct.pack("<IH", len(body) + 6, 0x2022) + body)
    payload = bytearray(source.read_bytes())
    frame_size = struct.unpack_from("<I", payload, 128)[0]
    count = struct.unpack_from("<H", payload, 134)[0]
    extra = b"".join(chunks)
    payload[128 + frame_size : 128 + frame_size] = extra
    struct.pack_into("<I", payload, 0, len(payload))
    struct.pack_into("<I", payload, 128, frame_size + len(extra))
    struct.pack_into("<H", payload, 134, count + len(chunks))
    struct.pack_into("<I", payload, 140, count + len(chunks))
    source.write_bytes(payload)


@pytest.mark.parametrize(
    ("frame", "address", "key_frame", "rectangle", "pixels"),
    [
        (
            2,
            {"slice_name": "animated"},
            1,
            {"x": 0, "y": 0, "width": 2, "height": 1},
            [(10, 30, 100, 255), (30, 30, 100, 255)],
        ),
        (
            4,
            {"slice_index": None},
            3,
            {"x": 2, "y": 1, "width": 2, "height": 2},
            [
                (50, 70, 200, 255),
                (70, 70, 200, 255),
                (50, 110, 200, 255),
                (70, 110, 200, 255),
            ],
        ),
    ],
)
def test_slice_uses_effective_animated_key(
    tmp_path: Path,
    frame: int,
    address: dict,
    key_frame: int,
    rectangle: dict,
    pixels: list,
) -> None:
    source = source_sprite(tmp_path, "static_geometry.lua")
    _animated_slices(source)
    before = source.read_bytes()
    destination = tmp_path / "slice.png"
    snapshot = spa(
        "slice",
        "list",
        "--input-json",
        json.dumps(
            {"sprite_file": str(source), "aseprite": os.environ["SPA_TEST_ASEPRITE"]}
        ),
    )
    assert snapshot.returncode == 0, snapshot.stdout + snapshot.stderr
    # Slice indexes address the current snapshot. Native import need not preserve
    # the order of Slice chunks in a file.
    index = next(
        item["slice_index"]
        for item in json.loads(snapshot.stdout)["slices"]
        if item["name"] == "animated"
    )
    if "slice_index" in address:
        address = {"slice_index": index}
    result = _export(
        _request(
            source,
            destination,
            frame_number=frame,
            export_image_area={"kind": "slice", "slice": address},
        )
    )
    resolved = result["export_image_area"]
    assert resolved["kind"] == "slice"
    assert resolved["slice_name"] == "animated" and resolved["slice_index"] == index
    assert resolved["key_frame_number"] == key_frame
    assert resolved["rectangle"] == rectangle
    with Image.open(destination) as image:
        assert image.size == (rectangle["width"], rectangle["height"])
        assert list(image.convert("RGBA").get_flattened_data()) == pixels
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    ("area", "reason"),
    [
        ({"kind": "slice", "slice": {"slice_name": "late"}}, "slice_key"),
        ({"kind": "slice", "slice": {"slice_name": "outside"}}, "area"),
        (
            {
                "kind": "rectangle",
                "rectangle": {"x": -1, "y": 0, "width": 2, "height": 1},
            },
            "area",
        ),
        (
            {
                "kind": "rectangle",
                "rectangle": {"x": 4, "y": 0, "width": 2, "height": 1},
            },
            "area",
        ),
    ],
)
@pytest.mark.parametrize("replace", [False, True])
def test_invalid_area_keeps_source_and_destination_unchanged(
    tmp_path: Path, area: dict, reason: str, replace: bool
) -> None:
    source = source_sprite(tmp_path, "static_geometry.lua")
    _animated_slices(source)
    before = source.read_bytes()
    destination = tmp_path / "failed.png"
    prior = b"existing destination must survive rejected export"
    if replace:
        destination.write_bytes(prior)
    request = _request(source, destination, export_image_area=area)
    request["destination"]["if_exists"] = "replace" if replace else "fail"
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode != 0, run.stdout
    failure = json.loads(run.stdout)
    assert failure["code"] == "export_image_invalid", failure
    assert failure["details"]["reason"] == reason
    assert source.read_bytes() == before
    assert destination.read_bytes() == prior if replace else not destination.exists()


def _persist_group_opacity(source: Path) -> None:
    # #117: native batch SaveAs drops persisted Group opacity. Independent test
    # fixture data sets the documented flag and bytes; no production repair.
    raw = bytearray(source.read_bytes())
    struct.pack_into("<I", raw, 14, struct.unpack_from("<I", raw, 14)[0] | 2)
    offset = 144
    group_number = 0
    for _ in range(struct.unpack_from("<H", raw, 134)[0]):
        size, kind = struct.unpack_from("<IH", raw, offset)
        if kind == 0x2004 and struct.unpack_from("<H", raw, offset + 8)[0] == 1:
            group_number += 1
            raw[offset + 18] = 128 if group_number == 1 else 255
        offset += size
    source.write_bytes(raw)


@pytest.mark.parametrize("selection", ["group", "leaf"])
def test_exact_group_or_layer_keeps_hidden_ancestor_opacity_context(
    tmp_path: Path, selection: str
) -> None:
    source = source_sprite(tmp_path, "sheet_sources.lua", variant="hidden_group")
    _persist_group_opacity(source)
    before = source.read_bytes()
    destination = tmp_path / "group.png"
    address = (
        {"layer_name": "selected"}
        if selection == "group"
        else {"layer_path": [2, 1, 1]}
    )
    result = _export(
        _request(
            source,
            destination,
            layer_composition={"mode": "include", "layers": [address]},
        )
    )
    assert result["resolved_layer_paths"] == [[2], [2, 1], [2, 1, 1]]
    with Image.open(destination) as image:
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (201, 17, 29, 128),
            (0, 0, 0, 0),
            (0, 0, 0, 0),
        ]
    assert source.read_bytes() == before


def test_visible_reference_exclusion_and_direct_reference_refusal(
    tmp_path: Path,
) -> None:
    source = source_sprite(tmp_path, "sheet_sources.lua", variant="reference")
    before = source.read_bytes()
    destination = tmp_path / "reference.png"
    request = _request(source, destination)
    _export(request)
    with Image.open(destination) as image:
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (200, 0, 0, 255),
            (0, 0, 0, 0),
        ]
    previous = destination.read_bytes()
    request["destination"]["if_exists"] = "replace"
    request["layer_composition"] = {
        "mode": "include",
        "layers": [{"layer_name": "reference"}],
    }
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode != 0
    failure = json.loads(run.stdout)
    assert failure["code"] == "export_image_invalid", failure
    assert failure["details"]["reason"] == "layer_composition"
    assert destination.read_bytes() == previous
    assert source.read_bytes() == before


def test_ordinary_and_tilemap_content_share_selected_rectangle(tmp_path: Path) -> None:
    source = source_sprite(tmp_path, "static_geometry.lua", variant="mixed_tilemap")
    before = source.read_bytes()
    destination = tmp_path / "tiles.png"
    result = _export(
        _request(
            source,
            destination,
            export_image_area={
                "kind": "rectangle",
                "rectangle": {"x": 1, "y": 0, "width": 3, "height": 1},
            },
            layer_composition={
                "mode": "include",
                "layers": [{"layer_name": "ordinary"}, {"layer_name": "tiles"}],
            },
        )
    )
    assert result["resolved_layer_paths"] == [[1], [2]]
    with Image.open(destination) as image:
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (11, 22, 33, 255),
            (0, 0, 0, 0),
            (200, 30, 40, 255),
        ]
    assert source.read_bytes() == before


@pytest.mark.parametrize("background", [False, True])
def test_indexed_preservation_and_rgb_visual_composition_are_explicit_paths(
    tmp_path: Path, background: bool
) -> None:
    source = source_sprite(
        tmp_path,
        "static_geometry.lua",
        variant="indexed_background" if background else "indexed",
    )
    before = source.read_bytes()
    preserved = tmp_path / "preserved.png"
    result = _export(_request(source, preserved))
    assert result["source_color_mode"] == result["color_mode"] == "indexed"
    assert result["transparent_index"] == 7
    assert result["effective_background"] is background
    expected_palette = [
        (0, 0, 0, 255),
        (200, 0, 0, 255),
        (0, 0, 200, 128),
        (200, 0, 0, 255),
        (40, 44, 48, 255),
        (50, 55, 60, 255),
        (60, 66, 72, 255),
        (70, 77, 84, 255 if background else 0),
    ]
    assert result["palette_entries"] == [
        dict(zip(("red", "green", "blue", "alpha"), color))
        for color in expected_palette
    ]
    with Image.open(preserved) as image:
        assert image.mode == "P" and image.size == (3, 1)
        assert list(image.get_flattened_data()) == [2, 7, 1]
        assert image.getpalette() == [
            channel for color in expected_palette for channel in color[:3]
        ]
        assert image.info["transparency"] == bytes(
            color[3] for color in expected_palette
        )
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (0, 0, 200, 128),
            (70, 77, 84, 255 if background else 0),
            (200, 0, 0, 255),
        ]
    visual = tmp_path / "visual.png"
    result = _export(_request(source, visual, composition_color_mode="rgb"))
    assert result["color_mode"] == "rgb" and result["source_color_mode"] == "indexed"
    assert result["transparent_index"] is None and result["palette_entries"] == []
    assert result["effective_background"] is background
    with Image.open(visual) as image:
        assert image.mode == ("RGB" if background else "RGBA")
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (100, 0, 100, 255),
            (70, 77, 84, 255) if background else (0, 0, 0, 0),
            (200, 0, 0, 255),
        ]
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    ("name", "code"), [("same", "slice_ambiguous"), ("absent", "slice_missing")]
)
def test_slice_address_refusal_preserves_owner_failure_and_existing_destination(
    tmp_path: Path, name: str, code: str
) -> None:
    source = source_sprite(tmp_path, "static_geometry.lua")
    _animated_slices(source)
    before = source.read_bytes()
    destination = tmp_path / "existing.png"
    prior = b"existing destination"
    destination.write_bytes(prior)
    request = _request(
        source,
        destination,
        export_image_area={"kind": "slice", "slice": {"slice_name": name}},
    )
    request["destination"]["if_exists"] = "replace"
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode != 0
    failure = json.loads(run.stdout)
    assert failure["code"] == code, failure
    assert failure["details"]["kind"] == "slice_target"
    assert failure["details"]["address"]["slice_name"] == name
    assert source.read_bytes() == before
    assert destination.read_bytes() == prior


@pytest.mark.parametrize(
    ("name", "code"), [("pattern", "layer_ambiguous"), ("absent", "layer_missing")]
)
def test_layer_address_refusal_preserves_owner_failure_and_existing_destination(
    tmp_path: Path, name: str, code: str
) -> None:
    source = source_sprite(tmp_path, "static_geometry.lua", variant="ambiguous_layer")
    before = source.read_bytes()
    destination = tmp_path / "existing.png"
    prior = b"existing destination"
    destination.write_bytes(prior)
    request = _request(
        source,
        destination,
        layer_composition={"mode": "include", "layers": [{"layer_name": name}]},
    )
    request["destination"]["if_exists"] = "replace"
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode != 0
    failure = json.loads(run.stdout)
    assert failure["code"] == code, failure
    assert failure["details"]["kind"] == "layer_target"
    assert failure["details"]["address_role"] == "target"
    assert failure["details"]["address"]["layer_name"] == name
    assert source.read_bytes() == before
    assert destination.read_bytes() == prior
