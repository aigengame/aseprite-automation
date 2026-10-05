"""Bounded animation delivery over retained wizard Sources; no recipe rebuild."""

import hashlib
import json
import os
from pathlib import Path

import pytest
from PIL import Image

from tests.support import spa

pytestmark = pytest.mark.e2e
REPOSITORY = Path(__file__).resolve().parents[2]
EXAMPLE = REPOSITORY / "examples/wizard_cast_v2"
DELIVERY = EXAMPLE / "godot/content/wizard_assets"


def _export(operation: str, source: Path, frames: list[int], destination: dict) -> dict:
    request = {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "playback": {"kind": "frames", "frame_numbers": frames},
        "layer_composition": {"mode": "visible"},
        "destination": destination,
    }
    run = spa("export", operation, "--input-json", json.dumps(request))
    assert run.returncode == 0, f"{run.stdout}\n{run.stderr}"
    result = json.loads(run.stdout)
    assert result["status"] == "success", result
    assert result["operation"] == f"spa export {operation}"
    occurrences = result["playback"]["occurrences"]
    assert [item["occurrence"] for item in occurrences] == list(
        range(1, len(frames) + 1)
    )
    assert [item["source_frame_number"] for item in occurrences] == frames
    assert [item["source_duration_ms"] for item in occurrences] == [100] * len(frames)
    return result


@pytest.mark.parametrize(
    ("source_name", "component", "frames", "size"),
    [
        ("wizard_scene", "scene", list(range(1, 33)), (384, 288)),
        ("background", "background", list(range(1, 33)), (384, 288)),
        ("wizard", "wizard", list(range(1, 33)), (256, 256)),
        ("gem", "gem", list(range(1, 33)), (104, 116)),
        ("burst", "burst", list(range(1, 33)), (176, 160)),
        ("projectile", "projectile", list(range(1, 33)), (72, 40)),
        ("target", "target", [1], (64, 84)),
        ("gem", "gem", [15, 7, 14, 1, 15], (104, 116)),
        ("projectile", "projectile", [1, 15, 20, 21, 15], (72, 40)),
    ],
)
def test_retained_wizard_sequence_preserves_order_canvas_and_decoded_pixels(
    tmp_path: Path,
    source_name: str,
    component: str,
    frames: list[int],
    size: tuple[int, int],
) -> None:
    source = EXAMPLE / "source" / f"{source_name}.aseprite"
    original = source.read_bytes()
    assert not original.startswith(b"version https://git-lfs.github.com/spec/v1"), (
        "This retained-asset test requires Git LFS content"
    )
    output = tmp_path / component
    output.mkdir()
    result = _export(
        "sequence",
        source,
        frames,
        {
            "directory": str(output),
            "filename_format": "output_{frame0001}.png",
            "if_exists": "fail",
        },
    )
    assert (result["width"], result["height"]) == size
    expected_names = [
        f"output_{ordinal:04}.png" for ordinal in range(1, len(frames) + 1)
    ]
    artifacts = result["artifacts"]
    assert [Path(item["path"]).name for item in artifacts] == expected_names
    assert {item.name for item in output.iterdir()} == set(expected_names)
    assert [item["source_frame_number"] for item in result["frames"]] == frames
    assert all(item["color_mode"] == "rgb" for item in result["frames"])
    assert all(item["color_profile"] == "srgb" for item in result["frames"])
    for artifact, source_frame, name in zip(
        artifacts, frames, expected_names, strict=True
    ):
        published = output / name
        payload = published.read_bytes()
        assert Path(artifact["path"]) == published
        assert artifact["byte_size"] == len(payload)
        assert artifact["sha256"] == hashlib.sha256(payload).hexdigest()
        with (
            Image.open(published) as actual,
            Image.open(DELIVERY / component / f"{source_frame:04}.png") as expected,
        ):
            assert actual.size == expected.size == size
            assert actual.mode == "RGBA"
            assert actual.info.get("srgb") == 0
            assert not actual.info.get("icc_profile")
            # Exact native RGBA includes colors under alpha-zero pixels.
            assert (
                actual.convert("RGBA").tobytes() == expected.convert("RGBA").tobytes()
            )
    assert source.read_bytes() == original


def _visible_rgba(image: Image.Image) -> bytes:
    payload = bytearray(image.convert("RGBA").tobytes())
    for offset in range(0, len(payload), 4):
        if payload[offset + 3] == 0:
            payload[offset : offset + 3] = bytes(3)
    return bytes(payload)


def test_retained_gem_gif_keeps_blank_repeated_occurrences_duration_and_infinite_loop(
    tmp_path: Path,
) -> None:
    source = EXAMPLE / "source/gem.aseprite"
    original = source.read_bytes()
    frames = [15, 7, 14, 1, 15]
    output = tmp_path / "gem.gif"
    result = _export("gif", source, frames, {"path": str(output), "if_exists": "fail"})
    assert len(result["artifacts"]) == 1
    artifact = result["artifacts"][0]
    assert Path(artifact["path"]) == output
    payload = output.read_bytes()
    assert artifact["byte_size"] == len(payload)
    assert artifact["sha256"] == hashlib.sha256(payload).hexdigest()
    with Image.open(output) as animation:
        assert animation.size == (104, 116)
        assert animation.info["loop"] == 0
        assert animation.n_frames == len(frames)
        assert not animation.info.get("icc_profile")
        for occurrence, source_frame in enumerate(frames):
            animation.seek(occurrence)
            assert animation.info["duration"] == 100
            rgba = animation.convert("RGBA")
            assert set(rgba.tobytes()[3::4]) <= {0, 255}
            with Image.open(DELIVERY / "gem" / f"{source_frame:04}.png") as expected:
                # This finite fixture has at most 20 colors. Equality here verifies
                # its native encoding; it creates no general exact-color GIF promise.
                assert _visible_rgba(rgba) == _visible_rgba(expected)
    assert source.read_bytes() == original
