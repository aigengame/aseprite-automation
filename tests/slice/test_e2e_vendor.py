"""Real native exporter output must pass complete Slice validation."""

import json
from pathlib import Path

import pytest

from tests.slice.support import fixture, native_script

pytestmark = pytest.mark.e2e
KERNEL = Path(__file__).parents[2] / "src/spa/kernel"


def _observation(tmp_path, mode):
    source = tmp_path / "source.aseprite"
    fixture(source)
    original = source.read_bytes()
    output = tmp_path / "result.json"
    native_script(
        "vendor_fault.lua",
        source=source,
        workspace=tmp_path,
        output=output,
        inspection=KERNEL / "document/sprite/sprite_inspect.lua",
        layer_select=KERNEL / "document/layer/layer_select.lua",
        slice_inspect=KERNEL / "document/slice/slice_inspect.lua",
        mode=mode,
    )
    assert source.read_bytes() == original
    assert not (tmp_path / "sprite-slices.png").exists()
    return json.loads(output.read_text())


@pytest.mark.parametrize(
    "mode",
    [
        "duplicate_frames",
        "unordered_frames",
        "fractional_frame",
        "outside_frame",
        "fractional_rectangle",
        "negative_dimensions",
        "fractional_pivot",
        "rectangle_array",
        "keys_object",
        "slices_object",
        "missing_keys",
        "missing_first_key",
        "missing_first_center",
        "missing_first_pivot",
        "different_first_bounds",
        "null_center",
        "bad_data_type",
        "different_data",
        "bad_color",
        "different_color",
        "missing_color",
        "no_write",
        "native_line_feed",
    ],
)
def test_slice_reader_rejects_malformed_or_missing_native_vendor_data(tmp_path, mode):
    result = _observation(tmp_path, mode)
    multi = next(item for item in result["baseline"] if item["name"] == "multi")
    assert [item["frame_number"] for item in multi["keys"]] == [1, 3, 5]
    assert result["accepted"] is False, result
    assert result["active_sprite_preserved"] is True
    assert result["active_frame_number"] == 4


def test_slice_reader_preserves_native_keyless_slice_without_synthetic_key(tmp_path):
    result = _observation(tmp_path, "keyless")
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
