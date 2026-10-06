"""Sprite Sheets through the public CLI and independent file decoders."""

import hashlib
import json
import os
import struct
from pathlib import Path

import pytest
from jsonschema import validate
from PIL import Image

from tests.export.support import png_icc_label, source_sprite
from tests.support import inject_palette_change, spa

pytestmark = pytest.mark.e2e


def sheet_request(source: Path, folder: Path) -> dict:
    return {
        "source_sprite_file": str(source),
        "image_destination": {"path": str(folder / "sheet.png"), "if_exists": "fail"},
        "metadata_destination": {
            "path": str(folder / "sheet.json"),
            "if_exists": "fail",
        },
        "selection": {"kind": "range", "from_frame": 1, "to_frame": 2},
        "layer_composition": {"mode": "visible"},
        "output_color_mode": "rgb",
        "layout": {"kind": "horizontal"},
        "trim": "none",
        "padding": {"border": 0, "shape": 0, "inner": 0},
        "filename_format": "wizard_{frame0001}",
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }


def test_sheet_publishes_two_verified_artifacts_without_changing_source(
    tmp_path: Path,
) -> None:
    source = source_sprite(tmp_path)
    before = source.read_bytes()
    request = sheet_request(source, tmp_path)

    run = spa("export", "sheet", "--input-json", json.dumps(request))

    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    validate(
        result, json.loads(spa("export", "sheet", "--schema").stdout)["result_schema"]
    )
    assert result["source_frames"] == [1, 2]
    assert result["width"] == 6 and result["height"] == 2
    metadata = json.loads((tmp_path / "sheet.json").read_text())
    assert [f["filename"] for f in metadata["frames"]] == ["wizard_0001", "wizard_0002"]
    assert [f["duration"] for f in metadata["frames"]] == [100, 100]
    assert metadata["meta"]["image"] == "sheet.png"
    with Image.open(tmp_path / "sheet.png") as image:
        assert image.size == (6, 2)
        rgba = image.convert("RGBA")
        assert rgba.getpixel((0, 0)) == (200, 10, 20, 255)
        assert rgba.getpixel((4, 0)) == (17, 34, 51, 128)
    for artifact, role, suffix in zip(
        result["artifacts"], ("image", "metadata"), ("png", "json"), strict=True
    ):
        path = tmp_path / f"sheet.{suffix}"
        assert artifact["role"] == role and artifact["path"] == str(path)
        assert artifact["byte_size"] == len(path.read_bytes())
        assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert source.read_bytes() == before


@pytest.mark.parametrize("mode", ["rgb", "grayscale"])
def test_sheet_does_not_quantize_nonindexed_sources_implicitly(
    tmp_path: Path, mode: str
) -> None:
    source = source_sprite(tmp_path, "rgb_profile_alpha.lua", mode=mode, profile="none")
    before = source.read_bytes()
    request = sheet_request(source, tmp_path)
    request.update(
        output_color_mode="indexed",
        selection={"kind": "range", "from_frame": 1, "to_frame": 1},
    )
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode != 0
    result = json.loads(run.stdout)
    assert result["code"] == "export_sheet_unsupported"
    assert result["details"]["reason"] == "source_color_mode"
    assert not (tmp_path / "sheet.png").exists()
    assert not (tmp_path / "sheet.json").exists()
    assert source.read_bytes() == before


def test_zero_based_names_are_output_ordinals_with_literal_prefix_and_suffix(
    tmp_path: Path,
) -> None:
    source = source_sprite(tmp_path)
    request = sheet_request(source, tmp_path)
    request.update(
        selection={"kind": "range", "from_frame": 2, "to_frame": 2},
        filename_format="wizard_{frame0000}.png",
    )
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["frames"][0]["filename"] == "wizard_0000.png"
    assert result["frames"][0]["source_frame"] == 2
    assert not (tmp_path / "wizard_0000.png").exists()


@pytest.mark.parametrize(
    "layout",
    [
        {"kind": "horizontal"},
        {"kind": "vertical"},
        {"kind": "rows", "columns": 2},
        {"kind": "columns", "rows": 2},
        {"kind": "packed"},
    ],
)
@pytest.mark.parametrize("trim", ["none", "sprite", "frame"])
def test_native_layouts_preserve_duplicate_and_blank_logical_frames(
    tmp_path: Path, layout: dict, trim: str
) -> None:
    source = source_sprite(tmp_path, "sheet_sources.lua", variant="duplicates")
    before = source.read_bytes()
    request = sheet_request(source, tmp_path)
    request.update(
        selection={"kind": "tag", "tag": {"tag_name": "action"}},
        layout=layout,
        trim=trim,
        padding={"border": 1, "shape": 2, "inner": 1},
    )
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["source_frames"] == [1, 2, 3, 4, 5]
    assert result["selected_tag"]["direction"] == "reverse"
    assert result["selected_tag"]["repeats"] == 2
    metadata = json.loads((tmp_path / "sheet.json").read_text())
    assert [f["duration"] for f in metadata["frames"]] == [70, 110, 230, 40, 50]
    rectangles = [tuple(f["frame"].values()) for f in metadata["frames"]]
    assert len(set(rectangles)) < 5
    with Image.open(tmp_path / "sheet.png") as opened:
        atlas = opened.convert("RGBA")
        for number, record in enumerate(metadata["frames"], 1):
            rect, offset = record["frame"], record["spriteSourceSize"]
            image = atlas.crop(
                (
                    rect["x"] + 1,
                    rect["y"] + 1,
                    rect["x"] + rect["w"] - 1,
                    rect["y"] + rect["h"] - 1,
                )
            )
            rebuilt = Image.new("RGBA", (8, 6))
            rebuilt.paste(image, (offset["x"], offset["y"]))
            expected = Image.new("RGBA", (8, 6))
            if number <= 3:
                expected.paste(
                    (201, 17, 29, 255), (5, 3, 7, 4) if number == 3 else (2, 1, 4, 2)
                )
            assert rebuilt.tobytes() == expected.tobytes()
            if trim == "frame" and number >= 4:
                assert image.size == (1, 1) and image.getpixel((0, 0)) == (0, 0, 0, 0)
    assert source.read_bytes() == before


@pytest.mark.parametrize("mask", [0, 7])
def test_indexed_sheet_preserves_full_palette_indexes_and_transparency(
    tmp_path: Path, mask: int
) -> None:
    source = source_sprite(
        tmp_path, "sheet_sources.lua", variant=f"indexed{mask}_linked"
    )
    before = source.read_bytes()
    request = sheet_request(source, tmp_path)
    request.update(output_color_mode="indexed", layout={"kind": "packed"})
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["output_color_mode"] == "indexed" and len(result["frames"]) == 2
    assert result["frames"][0]["rectangle"] == result["frames"][1]["rectangle"]
    with Image.open(tmp_path / "sheet.png") as image:
        assert image.mode == "P" and list(image.get_flattened_data()) == [1, 2, mask]
        assert len(image.getpalette()) == 24
        assert image.getpalette()[3:6] == image.getpalette()[9:12] == [201, 17, 29]
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (201, 17, 29, 255),
            (31, 100, 151, 128),
            (mask * 10, mask * 11, mask * 12, 0),
        ]
    assert source.read_bytes() == before


def test_linked_palette_changes_render_before_dedup_and_reject_incompatible_indexed(
    tmp_path: Path,
) -> None:
    source = source_sprite(tmp_path, "sheet_sources.lua", variant="indexed7_linked")
    palette = [(n * 10, n * 11, n * 12, 255) for n in range(8)]
    palette[1], palette[2], palette[3] = (
        (1, 230, 7, 255),
        (31, 100, 151, 128),
        (201, 17, 29, 255),
    )
    inject_palette_change(source, palette)
    before = source.read_bytes()
    request = sheet_request(source, tmp_path)
    request["layout"] = {"kind": "packed"}
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    frames = json.loads(run.stdout)["frames"]
    assert frames[0]["rectangle"] != frames[1]["rectangle"]
    with Image.open(tmp_path / "sheet.png") as image:
        rgba = image.convert("RGBA")
        for frame, expected in zip(
            frames, [(201, 17, 29, 255), (1, 230, 7, 255)], strict=True
        ):
            rect = frame["rectangle"]
            assert rgba.getpixel((rect["x"], rect["y"])) == expected
    request.update(output_color_mode="indexed")
    for key in ("image_destination", "metadata_destination"):
        request[key]["if_exists"] = "replace"
    old = [
        (tmp_path / filename).read_bytes() for filename in ("sheet.png", "sheet.json")
    ]
    failure = json.loads(
        spa("export", "sheet", "--input-json", json.dumps(request)).stdout
    )
    assert (
        failure["code"] == "export_sheet_unsupported"
        and failure["details"]["reason"] == "palette_mismatch"
    )
    assert old == [
        (tmp_path / filename).read_bytes() for filename in ("sheet.png", "sheet.json")
    ]
    request.update(
        selection={"kind": "range", "from_frame": 1, "to_frame": 1}, trim="sprite"
    )
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    assert source.read_bytes() == before


def test_subset_projects_complete_tags_and_keeps_whole_timeline_common_trim(
    tmp_path: Path,
) -> None:
    source = source_sprite(tmp_path, "sheet_sources.lua", variant="duplicates")
    request = sheet_request(source, tmp_path)
    request.update(
        selection={"kind": "tag", "tag": {"tag_name": "nested"}}, trim="sprite"
    )
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["source_frames"] == [2, 3]
    assert result["common_trim"] == {"x": 2, "y": 1, "width": 5, "height": 3}
    tags = json.loads((tmp_path / "sheet.json").read_text())["meta"]["frameTags"]
    assert {t["name"] for t in tags} == {"nested", "one"}
    assert next(t for t in tags if t["name"] == "nested") == {
        "name": "nested",
        "from": 0,
        "to": 1,
        "direction": "pingpong_reverse",
        "color": "#000000ff",
    }
    assert next(t for t in tags if t["name"] == "one")["from"] == 1


@pytest.mark.parametrize(
    "trim,success", [("none", False), ("sprite", False), ("frame", True)]
)
def test_indexed_background_conflict_is_decided_after_native_trim(
    tmp_path: Path, trim: str, success: bool
) -> None:
    source = source_sprite(
        tmp_path, "sheet_sources.lua", variant="background_indexed_mask"
    )
    before = source.read_bytes()
    request = sheet_request(source, tmp_path)
    request.update(
        output_color_mode="indexed",
        selection={"kind": "tag", "tag": {"tag_name": "first"}},
        trim=trim,
    )
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    result = json.loads(run.stdout)
    if success:
        assert run.returncode == 0, run.stdout + run.stderr
        assert result["effective_background"] is True
        assert result["frames"][0]["source_rectangle"] == {
            "x": 2,
            "y": 1,
            "width": 1,
            "height": 1,
        }
        with Image.open(tmp_path / "sheet.png") as image:
            assert image.convert("RGBA").getpixel((0, 0)) == (255, 0, 0, 255)
    else:
        assert (
            result["code"] == "export_sheet_unsupported"
            and result["details"]["reason"] == "background_transparency"
        )
        assert (
            not (tmp_path / "sheet.png").exists()
            and not (tmp_path / "sheet.json").exists()
        )
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "mode,output",
    [("rgb", "rgb"), ("grayscale", "rgb"), ("indexed", "rgb"), ("indexed", "indexed")],
)
@pytest.mark.parametrize("profile", ["none", "srgb", "linear_srgb", "display_p3"])
def test_sheet_preserves_supported_profiles_with_independent_icc_verification(
    tmp_path: Path, mode: str, output: str, profile: str
) -> None:
    icc = (
        Path(__file__).resolve().parents[2]
        / "src/spa/kernel/color/profiles"
        / f"{profile}.icc"
    )
    source = source_sprite(
        tmp_path,
        "rgb_profile_alpha.lua",
        mode=mode,
        two_frames="true",
        profile=profile if profile in ("none", "srgb") else "icc",
        icc_file=str(icc),
    )
    before = source.read_bytes()
    request = sheet_request(source, tmp_path)
    request.update(output_color_mode=output)
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    with Image.open(tmp_path / "sheet.png") as image:
        if profile in ("none", "srgb"):
            assert result["color_profile"] == profile
            assert "icc_profile" not in image.info
            assert image.info.get("srgb") == (0 if profile == "srgb" else None)
            assert result["srgb_rendering_intent"] == (0 if profile == "srgb" else None)
        else:
            assert (
                result["color_profile"] == "icc" and result["icc_identity"] == profile
            )
            assert image.info["icc_profile"] == icc.read_bytes()
            assert png_icc_label(
                (tmp_path / "sheet.png").read_bytes()
            ) == profile.encode("ascii")
        assert image.convert("RGBA").getpixel((0, 0)) == (
            (90, 90, 90, 127) if mode == "grayscale" else (11, 22, 33, 127)
        )
    assert source.read_bytes() == before


def test_explicit_group_includes_hidden_descendants_and_retains_native_opacity(
    tmp_path: Path,
) -> None:
    source = source_sprite(tmp_path, "sheet_sources.lua", variant="hidden_group")
    # #117: batch SaveAs omits persisted Group opacity. Supply an independent
    # file-format fixture, as the Image composition tests do, without production repair.
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
    before = source.read_bytes()
    request = sheet_request(source, tmp_path)
    request.update(
        selection={"kind": "range", "from_frame": 1, "to_frame": 1},
        layer_composition={"mode": "include", "layers": [{"layer_name": "selected"}]},
    )
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    with Image.open(tmp_path / "sheet.png") as image:
        rgba = image.convert("RGBA")
        assert rgba.getpixel((0, 0)) == (201, 17, 29, 128)
        assert rgba.getpixel((2, 0)) == (0, 0, 0, 0)
    assert source.read_bytes() == before


def test_reference_is_excluded_and_direct_reference_selection_is_refused(
    tmp_path: Path,
) -> None:
    source = source_sprite(tmp_path, "sheet_sources.lua", variant="reference")
    request = sheet_request(source, tmp_path)
    request["selection"] = {"kind": "range", "from_frame": 1, "to_frame": 1}
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    with Image.open(tmp_path / "sheet.png") as image:
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (200, 0, 0, 255),
            (0, 0, 0, 0),
        ]
    request["layer_composition"] = {
        "mode": "include",
        "layers": [{"layer_name": "reference"}],
    }
    for key in ("image_destination", "metadata_destination"):
        request[key]["if_exists"] = "replace"
    failure = json.loads(
        spa("export", "sheet", "--input-json", json.dumps(request)).stdout
    )
    assert (
        failure["code"] == "export_sheet_unsupported"
        and failure["details"]["reason"] == "reference_layer"
    )


@pytest.mark.parametrize("output", ["rgb", "indexed"])
def test_sheet_reuses_native_tilemap_composition(tmp_path: Path, output: str) -> None:
    source = source_sprite(tmp_path, "sheet_sources.lua", variant="tilemap")
    request = sheet_request(source, tmp_path)
    request.update(
        output_color_mode=output,
        selection={"kind": "range", "from_frame": 1, "to_frame": 1},
        layer_composition={"mode": "include", "layers": [{"layer_name": "tiles"}]},
    )
    run = spa("export", "sheet", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout + run.stderr
    with Image.open(tmp_path / "sheet.png") as image:
        rgba = image.convert("RGBA")
        assert rgba.getpixel((0, 0)) == (11, 22, 33, 255)
        assert rgba.getpixel((2, 0))[3] == 0
