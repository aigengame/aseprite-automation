"""Indexed admission follows native Frame ordering and explicit Palette time."""

import pytest

from tests.filter.support import native_script, observe_images, run
from tests.support import inject_palette_change

pytestmark = pytest.mark.e2e


def make_source(runtime, source):
    native_script(runtime, "pixel_filter_palette.lua", source=source)
    inject_palette_change(
        source, [(i, i, i, 0 if i == 0 else 255) for i in range(129)], frame_number=3
    )


def index_request(source, target, frames, basis):
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "color_mode": "indexed",
        "channels": {"kind": "index"},
        "palette_frame_number": basis,
        "cels_target": {
            "kind": "selected",
            "layers": [{"layer_path": [1]}],
            "frame_numbers": frames,
        },
        "selection": {
            "kind": "all",
            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
        },
    }


def test_linked_image_uses_earliest_selected_frame_representative(tmp_path, runtime):
    source, first, reversed_target = (
        tmp_path / name
        for name in ("source.aseprite", "first.aseprite", "reversed.aseprite")
    )
    make_source(runtime, source)
    for frames, target in [([1, 2], first), ([2, 1], reversed_target)]:
        request = index_request(source, target, frames, 3)
        request["selection"]["rectangle"]["x"] = 1
        code, result = run("filter", "invert-color", **request)
        assert code == 0, result
        assert result["processed_image_numbers"] == [1]
        assert result["palette_basis"] == {
            "frame_number": 3,
            "palette_frame_number": 3,
            "palette_size": 129,
        }
    assert observe_images(runtime, first) == observe_images(runtime, reversed_target)
    code, result = run(
        "filter",
        "invert-color",
        **index_request(source, tmp_path / "reversed-refused.aseprite", [2, 1], 3),
    )
    assert code == 2, result
    assert result["details"]["index_violations"][0]["frame_number"] == 1
    code, result = run(
        "filter",
        "invert-color",
        **index_request(source, tmp_path / "refused.aseprite", [2], 3),
    )
    assert code == 2, result
    assert result["code"] == "filter_index_out_of_bounds"
    assert result["details"]["index_violations"] == [
        {
            "layer_path": [1],
            "frame_number": 2,
            "canvas_position": {"x": 0, "y": 0},
            "source_index": 0,
            "result_index": 255,
        }
    ]


def test_effective_palette_frame_need_not_be_a_palette_change(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(runtime, source)
    code, result = run(
        "filter", "invert-color", **index_request(source, target, [2], 2)
    )
    assert code == 0, result
    assert result["palette_basis"] == {
        "frame_number": 2,
        "palette_frame_number": 1,
        "palette_size": 256,
    }


@pytest.mark.parametrize("in_place", [False, True])
def test_index_refusal_preserves_existing_target_and_source(
    tmp_path, runtime, in_place
):
    source = tmp_path / "source.aseprite"
    target = source if in_place else tmp_path / "target.aseprite"
    make_source(runtime, source)
    if not in_place:
        target.write_bytes(b"existing target remains")
    source_before, target_before = source.read_bytes(), target.read_bytes()
    request = index_request(source, target, [2], 3)
    request.update(in_place=in_place, overwrite=True)
    code, result = run("filter", "invert-color", **request)
    assert code == 2, result
    assert result["code"] == "filter_index_out_of_bounds"
    assert source.read_bytes() == source_before
    assert target.read_bytes() == target_before
