"""Image Resize intent is validated before the runtime is selected."""

from pathlib import Path

import pytest

from tests.native_invocation import run


@pytest.mark.parametrize(
    "options",
    [
        {"width": 0},
        {"method": "bicubic"},
        {"method": "nearest-neighbor", "palette_frame_number": 1},
        {"position_policy": {"kind": "pivot", "pivot_x": 1}},
        {
            "width": 2,
            "height": 2,
            "position_policy": {
                "kind": "pivot",
                "pivot_x": 2**31,
                "pivot_y": 0,
                "rounding": "floor",
            },
        },
    ],
)
def test_invalid_resize_intent_has_no_target_file(
    tmp_path: Path, options: dict
) -> None:
    target = tmp_path / "rejected.aseprite"
    request = {
        "source_sprite_file": str(tmp_path / "missing-source.aseprite"),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "width": 4,
        "height": 4,
        "method": "nearest-neighbor",
        "position_policy": {"kind": "keep"},
        **options,
    }

    outcome = run("image resize", request, aseprite="/missing/aseprite")

    assert outcome.returncode == 2, outcome.envelope
    assert outcome.envelope["code"] == "invalid_request"
    assert not target.exists()
