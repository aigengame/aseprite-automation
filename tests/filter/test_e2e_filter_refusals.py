"""Each Filter refuses Background Alpha and Tilemap pixels before publication."""

import pytest

from tests.filter.support import FIXTURES, observe_images, operation_filter_names
from tests.native_invocation import run, run_lua
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e

BACKGROUND_ALPHA = "Background Layer ignores Alpha Channel; convert it before filtering"
TILEMAP_PIXELS = "Tilemap pixel filtering is not supported by this Filter"
# Brightness/Contrast is not in these tables. Its request schema accepts no
# Alpha Channel (test_unit_brightness_contrast.py), and it filters Tilemap
# pixels in Manual Tileset Mode (test_e2e_filter_tilemaps.py).
FILTERS = [name for name in operation_filter_names() if name != "brightness-contrast"]
PARAMETERS = {
    "color-curve": {"points": [{"input": 100, "output": 0}]},
    "replace-color": {
        "from": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 0},
        "to": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 0},
        "tolerance": 255,
    },
    "invert-color": {},
    "outline": {
        "outline_color": {
            "kind": "rgba",
            "red": 211,
            "green": 157,
            "blue": 89,
            "alpha": 203,
        },
        "background_color": {
            "kind": "rgba",
            "red": 19,
            "green": 23,
            "blue": 29,
            "alpha": 255,
        },
        "place": "outside",
        "tiled_mode": "none",
        "matrix": {"kind": "preset", "name": "circle"},
    },
}


def layers(*numbers):
    """Return a selected Cel target for the Layer paths numbers at Frame 1."""
    return {
        "kind": "selected",
        "layers": [{"layer_path": [number]} for number in numbers],
        "frame_numbers": [1],
    }


TILEMAP_TARGETS = {"all": {"kind": "all"}, "mixed": layers(1, 2), "tilemap": layers(2)}


def apply_filter(name, source, target, cels_target, alpha=50):
    """Run an RGB `spa filter <name>` request on the Red and Alpha Channels.

    Return `(returncode, envelope)`. The request permits SPA to overwrite
    target. Hue/Saturation uses only the Alpha Channel, because a color Channel
    needs a color adjustment. alpha is its Alpha adjustment.
    """
    names = ["alpha"] if name == "hue-saturation" else ["red", "alpha"]
    selected = {
        "color_mode": "rgb",
        "channels": {"kind": "components", "names": names},
        "cels_target": cels_target,
    }
    if name == "hue-saturation":
        fields = {"application": {"kind": "pixels", **selected}, "alpha": alpha}
    elif name == "despeckle":
        fields = {"pixels": selected, "width": 3, "height": 1, "tiled_mode": "none"}
    else:
        fields = {**selected, **PARAMETERS[name]}
    outcome = run(
        f"filter {name}",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            **fields,
        },
    )
    return outcome.returncode, outcome.envelope


def assert_refused(code, result, reason, source, original, target):
    """Assert the exact refusal, the unchanged Source and the kept Target."""
    assert code != 0 and result["code"] == "filter_unsupported_document", result
    assert result["message"] == result["details"]["reason"] == reason
    assert source.read_bytes() == original
    assert target.read_bytes() == b"existing target"


@pytest.mark.parametrize("name", FILTERS)
def test_background_alpha_refuses_before_publication(tmp_path, runtime, name):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    lua = run_lua(
        FIXTURES / "hue_source.lua",
        runtime,
        source=source,
        mode="rgb",
        background="true",
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    # A zero Hue/Saturation Alpha adjustment also refuses: the rule reads only
    # the requested Channels.
    code, result = apply_filter(name, source, target, layers(1), alpha=0)
    assert_refused(code, result, BACKGROUND_ALPHA, source, original, target)


@pytest.mark.parametrize("target_kind", list(TILEMAP_TARGETS))
@pytest.mark.parametrize("name", FILTERS)
def test_resolved_tilemap_pixels_refuse_whole_request(
    tmp_path, runtime, name, target_kind
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    lua = run_lua(FIXTURES / "tilemap.lua", runtime, source=source, mode="rgb")
    assert lua.returncode == 0, process_diagnostics(lua)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    code, result = apply_filter(name, source, target, TILEMAP_TARGETS[target_kind])
    assert_refused(code, result, TILEMAP_PIXELS, source, original, target)


@pytest.mark.parametrize("name", FILTERS)
def test_ordinary_pixels_preserve_unrelated_tilemap(tmp_path, runtime, name):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    lua = run_lua(FIXTURES / "tilemap.lua", runtime, source=source, mode="rgb")
    assert lua.returncode == 0, process_diagnostics(lua)
    original = source.read_bytes()
    before = observe_images(runtime, source)
    code, result = apply_filter(name, source, target, layers(1))
    assert code == 0, result
    assert result["processed_image_numbers"] == [1]
    after = observe_images(runtime, target)
    assert after["tiles"] == before["tiles"]
    assert [cel for cel in after["cels"] if cel["layer"] == "Tilemap"] == [
        cel for cel in before["cels"] if cel["layer"] == "Tilemap"
    ]
    assert source.read_bytes() == original
