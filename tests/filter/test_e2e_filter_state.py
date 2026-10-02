"""Native Filter calls restore editor state and roll back failed mutations."""

import json
from pathlib import Path

import pytest

from spa.authoring.raster.color_curve import COLOR_CURVE_RESOURCE
from spa.authoring.raster.filter import FILTER_RESOURCES
from spa.authoring.raster.hue_saturation import HUE_SATURATION_RESOURCE
from spa.authoring.raster.replace_color import REPLACE_COLOR_RESOURCE
from tests.filter.support import apply, native_script, observe_images, pixels

pytestmark = pytest.mark.e2e


def _exercise_state(
    tmp_path: Path, runtime, kind: str, fault: bool, operation: str
) -> dict:
    response = tmp_path / f"{kind}-{'fault' if fault else 'success'}.json"
    kernel = Path(__file__).resolve().parents[2] / "src" / "spa" / "kernel"
    resources = {
        resource.parameter_name: kernel / resource.package_path
        for resource in FILTER_RESOURCES
    }
    if operation == "hue-saturation":
        resources[HUE_SATURATION_RESOURCE.parameter_name] = (
            kernel / HUE_SATURATION_RESOURCE.package_path
        )
    for name, resource in (
        ("color-curve", COLOR_CURVE_RESOURCE),
        ("replace-color", REPLACE_COLOR_RESOURCE),
    ):
        if operation == name:
            resources[resource.parameter_name] = kernel / resource.package_path
    if fault:
        key = {"palette": "palette", "tilemap": "filter_tiles"}.get(kind, "digest")
        resources[f"{key}_real"] = resources[key]
        resources[key] = Path(__file__).parent / "fixtures" / f"state_fault_{key}.lua"
    native_script(
        runtime,
        "state_filter.lua",
        response=response,
        kind=kind,
        fault=str(fault).lower(),
        workspace=tmp_path,
        **resources,
    )
    return json.loads(response.read_text())


@pytest.mark.parametrize(
    "operation,kind",
    [
        ("brightness-contrast", "pixels"),
        ("brightness-contrast", "palette"),
        ("brightness-contrast", "tilemap"),
        ("hue-saturation", "pixels"),
        ("hue-saturation", "palette"),
        ("color-curve", "pixels"),
        ("replace-color", "pixels"),
    ],
)
def test_filter_restores_editor_state_after_success(
    tmp_path: Path, runtime, kind: str, operation: str
) -> None:
    observed = _exercise_state(
        tmp_path, runtime, kind, fault=False, operation=operation
    )
    before, after = observed["before"], observed["after"]
    assert observed["success"] is True, observed
    assert before["target_selection"] == [True, False, True]
    assert before["prior_selection"] == [False, True]
    assert before["range_frames"] == [1, 2]
    for field in (
        "active_sprite_id",
        "active_layer_id",
        "active_frame_number",
        "range_layer_ids",
        "range_frames",
        "range_colors",
        "target_selection",
        "prior_selection",
    ):
        assert after[field] == before[field], (field, observed)
    if kind != "palette":
        assert after["target_image_bytes"] != before["target_image_bytes"]
        assert after["palette_red"] == before["palette_red"]
        if kind == "tilemap":
            assert after["tile_pixel"] != before["tile_pixel"]
    else:
        assert after["target_image_bytes"] == before["target_image_bytes"]
        assert after["palette_red"] == 120


@pytest.mark.parametrize(
    "operation,kind",
    [
        ("brightness-contrast", "pixels"),
        ("brightness-contrast", "palette"),
        ("brightness-contrast", "tilemap"),
        ("hue-saturation", "pixels"),
        ("hue-saturation", "palette"),
        ("color-curve", "pixels"),
        ("replace-color", "pixels"),
    ],
)
def test_filter_rolls_back_native_effect_and_restores_state_after_failure(
    tmp_path: Path, runtime, kind: str, operation: str
) -> None:
    observed = _exercise_state(tmp_path, runtime, kind, fault=True, operation=operation)
    assert observed["success"] is False, observed
    assert observed["native_effect_observed"] is True, observed
    expected = "Filter User Data" if kind == "tilemap" else "injected post-filter"
    assert expected in observed["error"]
    assert observed["after"] == observed["before"]


@pytest.mark.parametrize(
    "mode,brightness,contrast",
    [
        ("rgb", -100, -100),
        ("rgb", -100, 100),
        ("rgb", 100, -100),
        ("rgb", 100, 100),
        ("grayscale", 100, -100),
        ("indexed", -100, 100),
    ],
)
def test_extreme_values_match_independent_native_command(
    tmp_path: Path, runtime, mode: str, brightness: int, contrast: int
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    baseline = tmp_path / "native.aseprite"
    native_script(runtime, "source.lua", source=source, mode=mode)
    native_script(
        runtime,
        "state_native_baseline.lua",
        source=source,
        target=baseline,
        mode=mode,
        brightness=brightness,
        contrast=contrast,
    )
    channels = ["gray"] if mode == "grayscale" else ["red", "green", "blue"]
    application = pixels(mode, channels={"kind": "components", "names": channels})
    if mode == "indexed":
        application["palette_frame_number"] = 1
    code, result = apply(
        source, target, application, brightness=brightness, contrast=contrast
    )
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, baseline)
