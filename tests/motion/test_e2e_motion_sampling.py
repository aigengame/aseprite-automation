"""Native sampling and preservation of bounded Cel motion."""

from copy import deepcopy
from pathlib import Path

import pytest

from tests.motion.test_e2e_motion import curves, fixture, inspect, run_motion

pytestmark = pytest.mark.e2e


def assert_preserved(before: dict, after: dict, layer: str = "wizard") -> None:
    assert before["frames"] == after["frames"]
    assert before["transparent_index"] == after["transparent_index"]
    assert len(before["cels"]) == len(after["cels"])
    for old, new in zip(before["cels"], after["cels"], strict=True):
        for field in ("pixels", "width", "height", "z", "links", "frame", "layer"):
            assert new[field] == old[field]
        if old["layer"] != layer:
            assert new == old


def moved(after: dict, layer: str = "wizard") -> list[dict]:
    return [cel for cel in after["cels"] if cel["layer"] == layer]


@pytest.mark.parametrize(
    ("policy", "negative", "positive"),
    [
        ("toward-zero", 0, 0),
        ("floor", -1, 0),
        ("ceil", 0, 1),
        ("nearest-away-from-zero", -1, 1),
    ],
)
@pytest.mark.parametrize("interpolation", ["linear", "smoothstep"])
def test_half_ties_round_before_baseline_addition(
    tmp_path: Path, policy: str, negative: int, positive: int, interpolation: str
) -> None:
    source = fixture(tmp_path)
    before = inspect(source, tmp_path)
    request = curves()
    request["opacity"] = None
    request["position_offsets"].update(interpolation=interpolation, rounding=policy)
    # Linear samples +/-0.5 at Frame 2. Smoothstep(1/4)=5/32,
    # and +/-16 gives +/-2.5 at Frame 2.
    span = 2 if interpolation == "linear" else 16
    request["position_offsets"]["keys"][-1]["offset"] = {"x": -span, "y": span}
    code, result = run_motion(source, tmp_path / "out.aseprite", request)
    assert code == 0, result
    after = inspect(tmp_path / "out.aseprite", tmp_path)
    assert_preserved(before, after)
    first, second = moved(after)[:2]
    assert (first["x"], first["y"], first["opacity"]) == (-2, 2, 20)
    magnitude = 0 if interpolation == "linear" else 2
    assert (second["x"], second["y"], second["opacity"]) == (
        -1 - magnitude + negative,
        1 + magnitude + positive,
        40,
    )


@pytest.mark.parametrize(
    ("policy", "rounded_up"),
    [
        ("toward-zero", False),
        ("floor", False),
        ("ceil", True),
        ("nearest-away-from-zero", True),
    ],
)
@pytest.mark.parametrize("interpolation", ["linear", "smoothstep"])
def test_opacity_curve_rounds_half_ties_independently(
    tmp_path: Path, policy: str, rounded_up: bool, interpolation: str
) -> None:
    source = fixture(tmp_path, mode="grayscale")
    before = inspect(source, tmp_path)
    request = curves()
    request["position_offsets"] = None
    request["opacity"].update(interpolation=interpolation, rounding=policy)
    # Frame 2 samples 0.5 for linear and 2.5 for smoothstep.
    end = 2 if interpolation == "linear" else 16
    request["opacity"]["keys"] = [
        {"frame_number": 1, "opacity": 0},
        {"frame_number": 5, "opacity": end},
    ]
    target = tmp_path / "out.aseprite"
    code, result = run_motion(source, target, request)
    assert code == 0, result
    after = inspect(target, tmp_path)
    assert_preserved(before, after)
    assert (
        moved(after)[1]["opacity"]
        == (2 if interpolation == "smoothstep" else 0) + rounded_up
    )
    assert [(c["x"], c["y"]) for c in moved(after)] == [
        (c["x"], c["y"]) for c in moved(before)
    ]


def test_step_exact_interior_keys_and_independent_policies(tmp_path: Path) -> None:
    source = fixture(tmp_path, artwork="emblem")
    before = inspect(source, tmp_path)
    request = curves()
    request["position_offsets"] = {
        "interpolation": "step",
        "rounding": "ceil",
        "keys": [
            {"frame_number": 1, "offset": {"x": 0, "y": 0}},
            {"frame_number": 3, "offset": {"x": 7, "y": -7}},
            {"frame_number": 5, "offset": {"x": -3, "y": 3}},
        ],
    }
    request["opacity"] = {
        "interpolation": "linear",
        "rounding": "floor",
        "keys": [
            {"frame_number": 1, "opacity": 0},
            {"frame_number": 3, "opacity": 255},
            {"frame_number": 5, "opacity": 0},
        ],
    }
    target = tmp_path / "out.aseprite"
    code, result = run_motion(source, target, request)
    assert code == 0, result
    assert [cel["before"]["frame_number"] for cel in result["cels"]] == [1, 2, 3, 4, 5]
    assert [cel["after"]["opacity"] for cel in result["cels"]] == [0, 127, 255, 127, 0]
    after = inspect(target, tmp_path)
    assert_preserved(before, after, "emblem")
    assert [(c["x"], c["y"]) for c in moved(after, "emblem")] == [
        (-2, 2),
        (-1, 1),
        (7, -7),
        (8, -8),
        (-1, 1),
    ]
    assert [c["opacity"] for c in moved(after, "emblem")] == [0, 127, 255, 127, 0]


def test_smoothstep_floor_uses_exact_fraction(tmp_path: Path) -> None:
    source = fixture(tmp_path)
    request = curves()
    request.update(from_frame=1, to_frame=4, opacity=None)
    request["position_offsets"].update(interpolation="smoothstep", rounding="floor")
    request["position_offsets"]["keys"][-1] = {
        "frame_number": 4,
        "offset": {"x": -999, "y": 999},
    }
    target = tmp_path / "out.aseprite"
    code, result = run_motion(source, target, request)
    assert code == 0, result
    # At Frame 3, smoothstep(2/3)=20/27; -999*20/27=-740 exactly.
    assert [(c["x"], c["y"]) for c in moved(inspect(target, tmp_path))] == [
        (-2, 2),
        (-260, 260),
        (-740, 740),
        (-998, 998),
        (2, -2),
    ]


@pytest.mark.parametrize(
    ("mode", "mask", "artwork"),
    [
        ("rgb", 0, "wizard"),
        ("grayscale", 0, "emblem"),
        ("indexed", 7, "wizard"),
    ],
)
def test_single_frame_and_omitted_properties_preserve_native_pixels(
    tmp_path: Path, mode: str, mask: int, artwork: str
) -> None:
    source = fixture(tmp_path, mode=mode, mask=mask, artwork=artwork)
    before = inspect(source, tmp_path)
    request = curves()
    request.update(from_frame=3, to_frame=3, opacity=None)
    request["position_offsets"]["keys"] = [
        {"frame_number": 3, "offset": {"x": 2, "y": -2}},
    ]
    target = tmp_path / "position.aseprite"
    code, result = run_motion(source, target, request)
    assert code == 0, result
    after = inspect(target, tmp_path)
    assert_preserved(before, after, artwork)
    assert [(c["x"], c["y"], c["opacity"]) for c in moved(after, artwork)] == [
        (-2, 2, 20),
        (-1, 1, 40),
        (2, -2, 60),
        (1, -1, 80),
        (2, -2, 100),
    ]
    assert after["transparent_index"] == mask
    opacity_only = deepcopy(request)
    opacity_only["position_offsets"] = None
    opacity_only["opacity"] = {
        "interpolation": "step",
        "rounding": "floor",
        "keys": [
            {"frame_number": 3, "opacity": 0},
        ],
    }
    second = tmp_path / "opacity.aseprite"
    code, result = run_motion(source, second, opacity_only)
    assert code == 0, result
    final = inspect(second, tmp_path)
    assert_preserved(before, final, artwork)
    assert moved(final, artwork)[2]["opacity"] == 0
    assert [(c["x"], c["y"]) for c in moved(final, artwork)] == [
        (c["x"], c["y"]) for c in moved(before, artwork)
    ]


def test_frozen_input_determinism_changed_keys_and_relative_accumulation(
    tmp_path: Path,
) -> None:
    source = fixture(tmp_path)
    frozen = source.read_bytes()
    request = curves()
    request["opacity"] = None
    first, second, changed, repeated = (
        tmp_path / f"{name}.aseprite"
        for name in ("first", "second", "changed", "repeated")
    )
    for target in (first, second):
        code, result = run_motion(source, target, request)
        assert code == 0, result
    assert inspect(first, tmp_path) == inspect(second, tmp_path)
    assert source.read_bytes() == frozen
    revised = deepcopy(request)
    revised["position_offsets"]["keys"][-1]["offset"] = {"x": 4, "y": -4}
    code, result = run_motion(source, changed, revised)
    assert code == 0, result
    assert moved(inspect(first, tmp_path))[-1]["x"] == 4
    assert moved(inspect(changed, tmp_path))[-1]["x"] == 6
    code, result = run_motion(first, repeated, request)
    assert code == 0, result
    assert moved(inspect(repeated, tmp_path))[-1]["x"] == 6
