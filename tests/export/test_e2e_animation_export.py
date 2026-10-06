"""Native animation delivery through the public CLI and independent decoders."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from tests.export.test_e2e_export_image import _source
from tests.support import spa

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize(
    "directory",
    [
        "sequence",
        "literal-{frame0}",
        "literal-{title}",
        "literal-{path}-{frame01}-{tag}",
    ],
)
def test_sequence_treats_output_directory_as_literal(tmp_path: Path, directory: str):
    source = _source(tmp_path)
    original = source.read_bytes()
    output = tmp_path / directory
    output.mkdir()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": os.path.relpath(source),
        "playback": {"kind": "frames", "frame_numbers": [1, 1]},
        "layer_composition": {"mode": "visible"},
        "destination": {
            "directory": str(output),
            "filename_format": "frame{frame1}.png",
            "if_exists": "fail",
        },
    }

    run = spa("export", "sequence", "--input-json", json.dumps(request))

    pngs = set(tmp_path.rglob("*.png"))
    assert run.returncode == 0, (run.stdout, sorted(map(str, pngs)))
    expected = [output / "frame1.png", output / "frame2.png"]
    assert pngs == set(expected)
    assert [
        Path(item["path"]) for item in json.loads(run.stdout)["artifacts"]
    ] == expected
    assert {item.name for item in output.iterdir()} == {"frame1.png", "frame2.png"}
    assert {item.name for item in tmp_path.iterdir()} == {"source.aseprite", directory}
    for path in expected:
        with Image.open(path) as image:
            assert image.size == (3, 2)
            assert image.convert("RGBA").getpixel((0, 0)) == (200, 10, 20, 255)
    assert source.read_bytes() == original

    # A second export applies the same literal directory and preflight policy.
    refused = spa("export", "sequence", "--input-json", json.dumps(request))
    assert refused.returncode == 1, refused.stdout
    assert json.loads(refused.stdout)["details"]["reason"] == "destination_exists"
    request["destination"]["if_exists"] = "replace"
    replaced = spa("export", "sequence", "--input-json", json.dumps(request))
    assert replaced.returncode == 0, replaced.stdout
    assert set(tmp_path.rglob("*.png")) == set(expected)
    assert {item.name for item in output.iterdir()} == {"frame1.png", "frame2.png"}
    assert {item.name for item in tmp_path.iterdir()} == {"source.aseprite", directory}
    assert source.read_bytes() == original


def test_sequence_keeps_order_repeated_occurrences_and_full_canvas(tmp_path: Path):
    source = _source(tmp_path)
    original = source.read_bytes()
    output = tmp_path / "sequence"
    output.mkdir()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": [2, 1, 2]},
        "layer_composition": {"mode": "visible"},
        "destination": {
            "directory": str(output),
            "filename_format": "wizard_{frame0000}.png",
            "if_exists": "fail",
        },
    }
    run = spa("export", "sequence", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert [
        item["source_frame_number"] for item in result["playback"]["occurrences"]
    ] == [2, 1, 2]
    assert [Path(item["path"]).name for item in result["artifacts"]] == [
        "wizard_0000.png",
        "wizard_0001.png",
        "wizard_0002.png",
    ]
    assert {item.name for item in output.iterdir()} == {
        "wizard_0000.png",
        "wizard_0001.png",
        "wizard_0002.png",
    }
    for ordinal, frame in enumerate([2, 1, 2]):
        with Image.open(output / f"wizard_{ordinal:04}.png") as image:
            assert image.size == (3, 2)
            rgba = image.convert("RGBA")
            expected = (17, 34, 51, 128) if frame == 2 else (200, 10, 20, 255)
            assert rgba.getpixel((1 if frame == 2 else 0, 0)) == expected
    assert source.read_bytes() == original


def test_sequence_tag_traversal_does_not_expand_stored_repeats(tmp_path: Path):
    source = _source(tmp_path, "animation_frames.lua")
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "tag", "tag": {"tag_name": "cast"}},
        "layer_composition": {"mode": "visible"},
        "destination": {
            "directory": str(tmp_path),
            "filename_format": "cast_{frame001}.png",
            "if_exists": "fail",
        },
    }
    run = spa("export", "sequence", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["playback"]["mode"] == "tag_traversal"
    assert result["playback"]["tag"]["direction"] == "ping_pong"
    assert result["playback"]["tag"]["repeats"] == 0
    assert [f["source_frame_number"] for f in result["playback"]["occurrences"]] == [
        1,
        2,
        3,
        2,
    ]
    assert [f["source_duration_ms"] for f in result["playback"]["occurrences"]] == [
        19,
        27,
        103,
        27,
    ]
    for ordinal, red in enumerate([40, 80, 120, 80], 1):
        with Image.open(tmp_path / f"cast_{ordinal:03}.png") as image:
            assert image.convert("RGBA").getpixel((0, 0)) == (red, 10, 20, 255)


@pytest.mark.parametrize(
    "mode,background", [("grayscale", False), ("indexed", False), ("indexed", True)]
)
def test_sequence_preserves_native_mode_alpha_and_full_palette(
    tmp_path: Path, mode: str, background: bool
):
    source = _source(
        tmp_path,
        "animation_representation.lua",
        mode=mode,
        background=str(background).lower(),
        profile="none",
    )
    original = source.read_bytes()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": [2, 1, 2]},
        "layer_composition": {"mode": "visible"},
        "destination": {
            "directory": str(tmp_path),
            "filename_format": "native{frame1}.png",
            "if_exists": "fail",
        },
    }
    run = spa("export", "sequence", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    for artifact, facts in zip(result["artifacts"], result["frames"], strict=True):
        assert facts["color_mode"] == mode
        assert facts["color_profile"] == "none"
        with Image.open(artifact["path"]) as image:
            assert image.mode == ("P" if mode == "indexed" else "LA")
            if mode == "indexed":
                assert image.tobytes() == bytes([7, 1, 2])
                assert len(image.palette.palette) == 8 * 3
                assert image.convert("RGBA").getpixel((0, 0)) == (
                    140,
                    30,
                    40,
                    255 if background else 0,
                )
                assert image.convert("RGBA").getpixel((1, 0)) == (200, 10, 20, 128)
                assert facts["effective_palette"]["transparent_color_index"] == 7
            else:
                assert image.tobytes() == bytes([0, 0, 80, 128, 200, 255])
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "mode,profile",
    [
        ("rgb", "linear_srgb"),
        ("rgb", "display_p3"),
        ("indexed", "linear_srgb"),
        ("indexed", "display_p3"),
        ("grayscale", "srgb"),
    ],
)
def test_sequence_preserves_supported_profiles(tmp_path: Path, mode: str, profile: str):
    from spa.adapters.sequence_png import decode_sequence_png

    profile_path = Path("src/spa/kernel/color/profiles") / f"{profile}.icc"
    options = {"icc_file": str(profile_path.resolve())} if profile != "srgb" else {}
    source = _source(tmp_path, "animation_representation.lua", mode=mode, **options)
    original = source.read_bytes()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": [2, 1]},
        "layer_composition": {"mode": "visible"},
        "destination": {
            "directory": str(tmp_path),
            "filename_format": "profile{frame0}.png",
            "if_exists": "fail",
        },
    }
    run = spa("export", "sequence", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    for item in result["artifacts"]:
        observed = decode_sequence_png(Path(item["path"]).read_bytes())
        assert observed.color_profile == ("srgb" if profile == "srgb" else "icc")
        if profile != "srgb":
            assert observed.icc_bytes == profile_path.read_bytes()
        else:
            assert observed.srgb_rendering_intent == 0
    assert source.read_bytes() == original


def test_sequence_resolves_linked_cels_palette_per_occurrence(tmp_path: Path):
    from tests.support import inject_palette_change

    source = _source(tmp_path, "animation_representation.lua", mode="indexed")
    entries = [(i * 20, 30, 40, 255) for i in range(8)]
    entries[1] = entries[2] = (0, 50, 200, 128)
    inject_palette_change(source, entries, frame_number=2)
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": [2, 1, 2]},
        "layer_composition": {"mode": "visible"},
        "destination": {
            "directory": str(tmp_path),
            "filename_format": "palette{frame1}.png",
            "if_exists": "fail",
        },
    }
    run = spa("export", "sequence", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert [
        f["effective_palette"]["palette_frame_number"] for f in result["frames"]
    ] == [2, 1, 2]
    for item, expected in zip(
        result["artifacts"],
        [(0, 50, 200, 128), (200, 10, 20, 128), (0, 50, 200, 128)],
        strict=True,
    ):
        with Image.open(item["path"]) as image:
            assert image.tobytes() == bytes([7, 1, 2])
            assert image.convert("RGBA").getpixel((1, 0)) == expected


def test_gif_tag_traversal_quantizes_time_and_reports_infinite_loop(tmp_path: Path):
    from spa.adapters.gif import decode_gif

    source = _source(tmp_path, "animation_frames.lua")
    original = source.read_bytes()
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "tag", "tag": {"tag_name": "cast"}},
        "layer_composition": {"mode": "visible"},
        "destination": {"path": str(tmp_path / "cast.gif"), "if_exists": "fail"},
    }
    run = spa("export", "gif", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["loop"] == {"mode": "infinite", "encoded_count": 0}
    assert result["playback"]["tag"]["repeats"] == 0
    decoded = decode_gif((tmp_path / "cast.gif").read_bytes())
    assert decoded.loop_count == 0
    assert [frame.duration_ms for frame in decoded.frames] == [10, 20, 100, 20]
    assert [frame.rgba_bytes[:4] for frame in decoded.frames] == [
        bytes([red, 10, 20, 255]) for red in [40, 80, 120, 80]
    ]
    assert all(
        frame.rgba_bytes[7] == 255 and frame.rgba_bytes[11] == 0
        for frame in decoded.frames
    )
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "scenario,code",
    [
        ("residual", "artifact_verification_failed"),
        ("short", "animation_export_invalid"),
    ],
)
def test_gif_refuses_native_alpha_residue_and_subcentisecond_input(
    tmp_path: Path, scenario: str, code: str
):
    source = _source(tmp_path, "animation_gif_cases.lua", scenario=scenario)
    original = source.read_bytes()
    destination = tmp_path / "untouched.gif"
    destination.write_bytes(b"existing destination")
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": [1, 2, 3]},
        "layer_composition": {"mode": "visible"},
        "destination": {"path": str(destination), "if_exists": "replace"},
    }
    run = spa("export", "gif", "--input-json", json.dumps(request))
    result = json.loads(run.stdout)
    assert run.returncode != 0 and result["code"] == code, result
    assert "artifacts" not in result
    assert destination.read_bytes() == b"existing destination"
    assert source.read_bytes() == original
    if scenario == "residual":
        assert "alpha" in result["message"]


def test_gif_reports_allowed_native_rgb_loss(tmp_path: Path):
    source = _source(tmp_path, "animation_gif_cases.lua", scenario="lossy")
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": [3, 1, 3]},
        "layer_composition": {"mode": "visible"},
        "destination": {"path": str(tmp_path / "lossy.gif"), "if_exists": "fail"},
    }
    run = spa("export", "gif", "--input-json", json.dumps(request))
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["quantization"] == "aseprite_native_lossy"
    assert len(result["frames"]) == 3
    assert all(f["changed_rgb_pixels"] > 0 for f in result["frames"])
    assert all(len(f["color_table"]) <= 256 for f in result["frames"])
