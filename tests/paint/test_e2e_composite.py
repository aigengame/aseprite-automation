"""Native Snapshot composition through the installed SPA public boundary."""

import json
import os
from pathlib import Path

import pytest
from jsonschema import validate

from tests.support import spa

pytestmark = pytest.mark.e2e


def _call(*command: str, **request: object) -> tuple[int, dict]:
    run = spa(
        *command,
        "--input-json",
        "-",
        stdin=json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"], **request}),
    )
    assert run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)


def _create(path: Path) -> None:
    code, result = _call(
        "sprite",
        "create",
        target_sprite_file=str(path),
        width=3,
        height=2,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=False,
    )
    assert code == 0, result


def _snapshot(color: dict, width: int = 1, mode: str = "rgb") -> dict:
    return {
        "coordinate_space": "image-pixel",
        "color_mode": mode,
        "rectangle": {"x": 0, "y": 0, "width": width, "height": 1},
        "rows": [[{"length": width, "color": color}]],
    }


def _compose(source: Path, target: Path, value: dict, **options: object):
    return _call(
        "paint",
        "composite",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        **{
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "input": {"kind": "inline", "snapshot": value},
            "position": {"x": 1, "y": 1},
            "opacity": 255,
            "blend_mode": "normal",
            **options,
        },
    )


def test_composite_persists_native_alpha_at_declared_image_position(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _create(source)
    original = source.read_bytes()
    color = {"kind": "rgba", "red": 240, "green": 80, "blue": 20, "alpha": 128}
    value = _snapshot(color)

    code, result = _compose(source, target, value)

    assert code == 0, result
    schema = json.loads(spa("paint", "composite", "--schema").stdout)
    validate(result, schema["result_schema"])
    assert result["pixels_changed"] == result["pixels_written"] == 1
    assert result["persisted_reopen_verified"] is True
    assert result["geometry_unchanged"] is True
    assert source.read_bytes() == original
    code, reopened = _call(
        "image",
        "get",
        sprite_file=str(target),
        source={
            "kind": "individual",
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "rectangle": {"x": 1, "y": 1, "width": 1, "height": 1},
        },
    )
    assert code == 0, reopened
    assert reopened["snapshot"] == value


def test_composite_partitions_clipping_and_explicit_selection(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _create(source)
    value = _snapshot(
        {"kind": "rgba", "red": 9, "green": 20, "blue": 30, "alpha": 255}, width=4
    )
    selected = {"kind": "all", "rectangle": {"x": 2, "y": 0, "width": 1, "height": 1}}

    code, result = _compose(
        source,
        target,
        value,
        position={"x": 1, "y": 0},
        clipping="clip",
        selection=selected,
    )

    assert code == 0, json.dumps(result)
    assert result["selection"] == selected
    assert result["pixels_requested"] == 4
    assert result["pixels_changed"] == result["pixels_written"] == 1
    assert result["applied_runs"] == [{"x": 2, "y": 0, "length": 1}]
    assert result["skipped_by_bounds_runs"] == [{"x": 3, "y": 0, "length": 2}]
    assert result["skipped_by_selection_runs"] == [{"x": 1, "y": 0, "length": 1}]


@pytest.mark.parametrize("opacity,alpha", [(0, 0), (127, 64)])
def test_composite_uses_explicit_native_opacity(
    tmp_path: Path, opacity: int, alpha: int
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _create(source)
    color = {"kind": "rgba", "red": 240, "green": 80, "blue": 20, "alpha": 128}
    code, result = _compose(source, target, _snapshot(color), opacity=opacity)
    assert code == 0, json.dumps(result)
    code, pixels = _call(
        "image",
        "get",
        sprite_file=str(target),
        source={
            "kind": "individual",
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "rectangle": {"x": 1, "y": 1, "width": 1, "height": 1},
        },
    )
    assert code == 0, pixels
    # Native Normal retains source RGB over an alpha-zero backdrop even at opacity 0
    # (Aseprite blend_funcs.cpp rgba_blender_normal, alpha-zero branch).
    expected = {**color, "alpha": alpha}
    assert pixels["snapshot"]["rows"] == [[{"length": 1, "color": expected}]]
