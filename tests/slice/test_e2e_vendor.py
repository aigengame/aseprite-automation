"""Real native exporter output must pass complete Slice validation."""

import json
import re
from pathlib import Path

import pytest

from tests.native_invocation import run_lua
from tests.slice.support import FIXTURES, UNESCAPED_LINE_BREAK, fixture
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e
KERNEL = Path(__file__).parents[2] / "src/spa/kernel"


def _observation(runtime, tmp_path, mode):
    """Return the `vendor_fault.lua` result for mode.

    Also check that the fixture keeps the source and writes no exporter image.
    """
    source = tmp_path / "source.aseprite"
    fixture(runtime, source)
    original = source.read_bytes()
    output = tmp_path / "result.json"
    lua = run_lua(
        FIXTURES / "vendor_fault.lua",
        runtime,
        source=source,
        workspace=tmp_path,
        output=output,
        inspection=KERNEL / "document/sprite/sprite_inspect.lua",
        layer_select=KERNEL / "document/layer/layer_select.lua",
        slice_inspect=KERNEL / "document/slice/slice_inspect.lua",
        mode=mode,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.read_bytes() == original
    assert not (tmp_path / "sprite-slices.png").exists()
    return json.loads(output.read_text())


FRAME = "Slice Key has an invalid or unordered Frame"
FIRST_KEY = "Slice vendor first Key differs from the opened Sprite"
NOT_RECTANGLE = "Slice Key Rectangle is not an object"
COLOR = "Slice vendor color differs from the opened Sprite"


# Each error was measured with Aseprite 1.3.18.5. The shape faults are on Key 2,
# so the first-Key cross-check cannot refuse them.
VENDOR_FAULTS = [
    ("duplicate_frames", FRAME),
    ("unordered_frames", FRAME),
    ("fractional_frame", FRAME),
    ("outside_frame", FRAME),
    ("fractional_rectangle", "Slice Key Rectangle has invalid coordinates"),
    ("negative_dimensions", "Slice Key Rectangle has invalid dimensions"),
    ("fractional_pivot", "Slice Key Point has invalid coordinates"),
    ("rectangle_array", NOT_RECTANGLE),
    ("keys_object", "Slice vendor Keys are not an array"),
    ("slices_object", "Slice vendor data has no Slice array"),
    ("missing_keys", "Slice vendor entry has no explicit Keys"),
    ("missing_first_key", FIRST_KEY),
    ("missing_first_center", FIRST_KEY),
    ("missing_first_pivot", FIRST_KEY),
    ("different_first_bounds", FIRST_KEY),
    ("null_center", NOT_RECTANGLE),
    ("bad_data_type", "Slice vendor user data is not a string"),
    ("different_data", "Slice vendor user data differs from the opened Sprite"),
    ("bad_color", "Slice vendor color is not RGBA hexadecimal"),
    ("different_color", COLOR),
    ("missing_color", COLOR),
    ("no_write", "could not open Slice vendor data"),
    ("native_line_feed", UNESCAPED_LINE_BREAK),
]


@pytest.mark.parametrize(
    ("mode", "error"), VENDOR_FAULTS, ids=[mode for mode, _ in VENDOR_FAULTS]
)
def test_slice_reader_rejects_malformed_or_missing_native_vendor_data(
    tmp_path, runtime, mode, error
):
    result = _observation(runtime, tmp_path, mode)
    multi = next(item for item in result["baseline"] if item["name"] == "multi")
    assert [item["frame_number"] for item in multi["keys"]] == [1, 3, 5]
    assert result["accepted"] is False, result
    assert re.fullmatch(
        rf".*slice_inspect\.lua:\d+: {re.escape(error)}", result["result"]
    ), result["result"]
    assert result["active_sprite_preserved"] is True
    assert result["active_frame_number"] == 4


def test_slice_reader_preserves_native_keyless_slice_without_synthetic_key(
    tmp_path, runtime
):
    result = _observation(runtime, tmp_path, "keyless")
    assert result["accepted"] is True, result
    empty = next(
        item for item in result["result"]["slices"] if item["name"] == "keyless"
    )
    assert empty == {
        "name": "keyless",
        "data": "native empty Slice",
        "color": {"red": 0, "green": 0, "blue": 0, "alpha": 0},
        "keys": [],
    }
