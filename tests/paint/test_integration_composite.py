"""Paint Composite refusals before the runtime probe, without Aseprite."""

from pathlib import Path

import pytest

from tests.native_invocation import run


def _snapshot(mode: str, *colors: dict) -> dict:
    return {
        "coordinate_space": "image-pixel",
        "color_mode": mode,
        "rectangle": {"x": 0, "y": 0, "width": len(colors), "height": 1},
        "rows": [[{"length": 1, "color": color} for color in colors]],
    }


RGB = _snapshot("rgb", {"kind": "rgba", "red": 1, "green": 2, "blue": 3, "alpha": 255})
INDEXED = {
    "input": {
        "kind": "inline",
        "snapshot": _snapshot(
            "indexed",
            {"kind": "palette-index", "index": 7},
            {"kind": "palette-index", "index": 8},
        ),
    },
    "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
}


@pytest.mark.parametrize(
    ("case", "change", "code"),
    [
        ("palette-for-rgb", {"palette_frame_number": 1}, "paint_composite_invalid"),
        ("malformed-artifact", {}, "paint_composite_invalid"),
        ("position-range", {"position": {"x": 2**53 + 1, "y": 0}}, "invalid_request"),
        # An Indexed Snapshot needs the Effective Palette of the target Frame.
        ("indexed-palette-missing", INDEXED, "paint_composite_invalid"),
        (
            "indexed-palette-of-other-frame",
            {**INDEXED, "palette_frame_number": 1},
            "paint_composite_invalid",
        ),
    ],
)
def test_invalid_composite_preserves_source_and_existing_target(
    tmp_path: Path, case: str, change: dict, code: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"Source Sprite")
    target.write_bytes(b"existing target")
    if case == "malformed-artifact":
        artifact = tmp_path / "invalid.json"
        artifact.write_text('{"color_mode":"rgb"}')
        change = {"input": {"kind": "artifact", "path": str(artifact)}}
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "input": {"kind": "inline", "snapshot": RGB},
        "position": {"x": 1, "y": 1},
        "opacity": 255,
        "blend_mode": "normal",
        **change,
    }

    outcome = run("paint composite", request, aseprite="/missing/aseprite")

    # The runtime probe would refuse the missing executable with exit 1.
    assert outcome.returncode == 2, outcome.envelope
    assert outcome.envelope["code"] == code
    assert source.read_bytes() == b"Source Sprite"
    assert target.read_bytes() == b"existing target"
    assert {item.name for item in tmp_path.iterdir()} - {"invalid.json"} == {
        "source.aseprite",
        "target.aseprite",
    }
