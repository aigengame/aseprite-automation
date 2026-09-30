"""Whole-Image orientation through the installed CLI and native persisted pixels."""

import json
import os
import subprocess
import tempfile
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import validate

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e


def _native(script: str, **parameters: object) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    with tempfile.TemporaryDirectory(prefix="spa-orientation-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        args = [str(prepared.executable), "--batch"]
        for key, value in parameters.items():
            args.extend(("--script-param", f"{key}={value}"))
        args.extend(("--script", str(Path(__file__).parent / "fixtures" / script)))
        run = subprocess.run(
            args, capture_output=True, text=True, env=prepared.environment, check=False
        )
    assert run.returncode == 0, process_diagnostics(run)


def _fixture(tmp_path: Path, mode: str = "rgb", kind: str = "regular") -> Path:
    source = tmp_path / "source.aseprite"
    _native("orientation_targets.lua", out=source, mode=mode, kind=kind)
    assert source.is_file()
    return source


def _inspect(source: Path, tmp_path: Path, layer: int = 1) -> dict:
    output = tmp_path / "native.json"
    _native("inspect_orientation.lua", source=source, out=output, layer=layer)
    return json.loads(output.read_text())


def _run(
    operation: str, source: Path, target_file: Path, **options: object
) -> tuple[int, dict]:
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target_file),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        **options,
    }
    run = spa("image", operation, "--input-json", json.dumps(request))
    return run.returncode, json.loads(run.stdout)


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize(
    ("axis", "order"),
    [("horizontal", [2, 1, 0, 5, 4, 3]), ("vertical", [3, 4, 5, 0, 1, 2])],
)
def test_flip_shared_image_once_and_keep_all_cel_positions(
    tmp_path: Path, mode: str, axis: str, order: list[int]
) -> None:
    source = _fixture(tmp_path, mode)
    before = _inspect(source, tmp_path)
    target = tmp_path / "flipped.aseprite"
    status, result = _run("flip", source, target, axis=axis)
    assert status == 0, result
    validate(
        result, json.loads(spa("image", "flip", "--schema").stdout)["result_schema"]
    )
    assert result["axis"] == axis
    assert result["old_size"] == result["new_size"] == {"width": 3, "height": 2}
    assert result["native_sharing_preserved"] is True
    assert result["persisted_reopen_verified"] is True
    assert len(result["affected_cels"]) == 2
    after = _inspect(target, tmp_path)
    expected = [before["cels"][0]["pixels"][index] for index in order]
    for cel in after["cels"][:2]:
        assert cel["pixels"] == expected
        assert cel["position"] == {"x": 4, "y": 5}
        assert len(cel["linked_frames"]) == 1
    assert after["cels"][2] == before["cels"][2]
    assert after["transparent_color_index"] == before["transparent_color_index"]


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize(
    ("angle", "size", "order"),
    [
        (90, (2, 3), [3, 0, 4, 1, 5, 2]),
        (-90, (2, 3), [2, 5, 1, 4, 0, 3]),
        (180, (3, 2), [5, 4, 3, 2, 1, 0]),
    ],
)
def test_quarter_turn_swaps_non_square_dimensions_and_preserves_pixel_values(
    tmp_path: Path,
    mode: str,
    angle: int,
    size: tuple[int, int],
    order: list[int],
) -> None:
    source = _fixture(tmp_path, mode)
    before = _inspect(source, tmp_path)
    target = tmp_path / "rotated.aseprite"
    status, result = _run(
        "rotate", source, target, angle=angle, position_policy={"kind": "keep"}
    )
    assert status == 0, result
    validate(
        result, json.loads(spa("image", "rotate", "--schema").stdout)["result_schema"]
    )
    assert result["angle"] == angle
    assert result["old_size"] == {"width": 3, "height": 2}
    assert result["new_size"] == {"width": size[0], "height": size[1]}
    assert result["position_delta"] == {"x": 0, "y": 0}
    after = _inspect(target, tmp_path)
    expected = [before["cels"][0]["pixels"][index] for index in order]
    for current in after["cels"][:2]:
        assert current["pixels"] == expected
        assert current["position"] == {"x": 4, "y": 5}
        assert len(current["linked_frames"]) == 1
    assert after["cels"][2] == before["cels"][2]
    assert after["transparent_color_index"] == before["transparent_color_index"]


@pytest.mark.parametrize(
    ("angle", "delta"), [(90, (1, 6)), (-90, (-6, 0)), (180, (-6, 7))]
)
def test_rotation_anchors_outside_image_pivot_and_moves_linked_cels_once(
    tmp_path: Path, angle: int, delta: tuple[int, int]
) -> None:
    source = _fixture(tmp_path)
    before = _inspect(source, tmp_path)
    target = tmp_path / "pivot.aseprite"
    policy = {"kind": "pivot", "pivot_x": -2, "pivot_y": 4}
    status, result = _run("rotate", source, target, angle=angle, position_policy=policy)
    assert status == 0, result
    assert result["position_policy"] == policy
    assert result["position_delta"] == {"x": delta[0], "y": delta[1]}
    after = _inspect(target, tmp_path)
    for current in after["cels"][:2]:
        assert current["position"] == {"x": 4 + delta[0], "y": 5 + delta[1]}
        assert len(current["linked_frames"]) == 1
    assert after["cels"][2] == before["cels"][2]


@pytest.mark.parametrize(
    ("angle", "pivot", "attempted_position", "in_place"),
    [
        (90, 32767, {"x": 65537, "y": 5}, True),
        (-90, -32768, {"x": 4, "y": -65533}, False),
    ],
)
def test_rotation_reports_placement_bounds_without_publishing(
    tmp_path: Path,
    angle: int,
    pivot: int,
    attempted_position: dict,
    in_place: bool,
) -> None:
    source = _fixture(tmp_path)
    original = source.read_bytes()
    target = source if in_place else tmp_path / "existing-target.aseprite"
    if not in_place:
        target.write_bytes(original)
    status, result = _run(
        "rotate",
        source,
        target,
        in_place=in_place,
        overwrite=True,
        target={"layer": {"layer_path": [1]}, "frame_number": 2},
        angle=angle,
        position_policy={"kind": "pivot", "pivot_x": pivot, "pivot_y": pivot},
    )
    assert status == 2
    assert result["code"] == "image_rotate_position_out_of_bounds", result
    assert source.read_bytes() == target.read_bytes() == original
    details = result["details"]
    assert details["allowed_minimum"] == -32768
    assert details["allowed_maximum"] == 32767
    assert details["coordinate_space"] == "canvas-pixel"
    assert details["attempted_position"] == attempted_position
    assert details["kind"] == "image_rotate_position"
    assert details["target"]["layer"]["layer_path"] == [1]
    assert details["target"]["frame_number"] == 2
    schema = json.loads(spa("image", "rotate", "--schema").stdout)["failure_schema"]
    validate(result, schema)


@pytest.mark.parametrize(("kind", "layer"), [("background", 1), ("reference", 1)])
@pytest.mark.parametrize("axis", ["horizontal", "vertical"])
def test_flip_preserves_background_and_reference_placement(
    tmp_path: Path, kind: str, layer: int, axis: str
) -> None:
    source = _fixture(tmp_path, kind=kind)
    inspected = _inspect(source, tmp_path, layer)
    assert inspected[f"is_{kind}"] is True
    before = inspected["cels"][0]
    target = tmp_path / "special-flipped.aseprite"
    status, result = _run(
        "flip",
        source,
        target,
        axis=axis,
        target={"layer": {"layer_path": [layer]}, "frame_number": 1},
    )
    assert status == 0, result
    after = _inspect(target, tmp_path, layer)["cels"][0]
    width, height = before["width"], before["height"]
    assert after["width"] == width and after["height"] == height
    assert after["position"] == before["position"]
    assert (
        result["affected_cels"][0]["before_bounds"]
        == result["affected_cels"][0]["after_bounds"]
    )
    expected = []
    for y in range(height):
        for x in range(width):
            old_x = width - 1 - x if axis == "horizontal" else x
            old_y = height - 1 - y if axis == "vertical" else y
            expected.append(before["pixels"][old_y * width + old_x])
    assert after["pixels"] == expected


@pytest.mark.parametrize(
    ("operation", "kind", "layer", "frame", "code"),
    [
        ("rotate", "background", 1, 1, "cel_unsupported_target"),
        ("rotate", "reference", 1, 1, "cel_unsupported_target"),
        *[
            (operation, kind, layer, frame, code)
            for operation in ("flip", "rotate")
            for kind, layer, frame, code in (
                ("group", 2, 1, "cel_unsupported_target"),
                ("tilemap", 2, 1, "cel_unsupported_target"),
                ("absent", 1, 1, "cel_not_found"),
                ("regular", 1, 4, "cel_frame_out_of_bounds"),
            )
        ],
    ],
)
def test_unsupported_target_rejection_preserves_existing_source_and_target(
    tmp_path: Path, operation: str, kind: str, layer: int, frame: int, code: str
) -> None:
    source = _fixture(tmp_path, kind=kind)
    original = source.read_bytes()
    target = tmp_path / "preserved.aseprite"
    target.write_bytes(original)
    options = (
        {"axis": "horizontal"}
        if operation == "flip"
        else {
            "angle": 90,
            "position_policy": {"kind": "keep"},
        }
    )
    status, result = _run(
        operation,
        source,
        target,
        overwrite=True,
        target={"layer": {"layer_path": [layer]}, "frame_number": frame},
        **options,
    )
    assert status == 2, result
    assert result["code"] == code, result
    assert source.read_bytes() == target.read_bytes() == original


@pytest.mark.parametrize(
    ("operation", "options", "pixels"),
    [
        ("flip", {"axis": "horizontal"}, [3, 2, 1, 6, 5, 4]),
        ("flip", {"axis": "vertical"}, [4, 5, 6, 1, 2, 3]),
        ("rotate", {"angle": 90}, [4, 1, 5, 2, 6, 3]),
        ("rotate", {"angle": -90}, [3, 6, 2, 5, 1, 4]),
        ("rotate", {"angle": 180}, [6, 5, 4, 3, 2, 1]),
    ],
)
def test_native_transform_ignores_active_selection(
    tmp_path: Path, operation: str, options: dict, pixels: list[int]
) -> None:
    output = tmp_path / "selected.json"
    _native(
        "orientation_selection.lua",
        out=output,
        operation=operation,
        **options,
        image_orientation_transform=files("spa.kernel").joinpath(
            "raster/image/image_orientation_transform.lua"
        ),
    )
    result = json.loads(output.read_text())
    assert result["pixels"] == pixels
    assert result["selection"] == {"x": 4, "y": 5, "width": 1, "height": 1}
    assert result["same_context"] is True
