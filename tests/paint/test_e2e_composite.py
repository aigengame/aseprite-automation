"""Native Snapshot composition through the installed SPA public boundary."""

import json
import os
from pathlib import Path

import pytest
from jsonschema import validate

from tests.image.support import image_fixture
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


def _compose(source_file: Path, target_file: Path, value: dict, **options: object):
    return _call(
        "paint",
        "composite",
        **{
            "source_sprite_file": str(source_file),
            "target_sprite_file": str(target_file),
            "in_place": False,
            "overwrite": False,
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


@pytest.mark.parametrize(
    "case", ["bounds", "color-mode", "palette-for-rgb", "malformed-artifact"]
)
def test_invalid_composite_preserves_source_and_existing_target(
    tmp_path: Path, case: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _create(source)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    value = _snapshot({"kind": "rgba", "red": 1, "green": 2, "blue": 3, "alpha": 255})
    options: dict = {"overwrite": True}
    if case == "bounds":
        options["position"] = {"x": -1, "y": 0}
    elif case == "color-mode":
        value = _snapshot(
            {"kind": "grayscale", "gray": 90, "alpha": 128}, mode="grayscale"
        )
    elif case == "palette-for-rgb":
        options["palette_frame_number"] = 1
    else:
        invalid = tmp_path / "invalid.json"
        invalid.write_text('{"color_mode":"rgb"}')
        options["input"] = {"kind": "artifact", "path": str(invalid)}
    code, result = _compose(source, target, value, **options)
    assert code != 0, result
    assert result["code"] == "paint_composite_invalid"
    assert source.read_bytes() == original
    assert target.read_bytes() == b"existing target"
    assert not list(tmp_path.glob("*.spa-stage-*"))


@pytest.mark.parametrize(
    "kind,layer,frame,code",
    [
        ("reference", 1, 1, "cel_unsupported_target"),
        ("tilemap", 2, 1, "cel_unsupported_target"),
        ("absent", 1, 2, "cel_not_found"),
    ],
)
def test_composite_rejects_unsupported_cel_targets(
    tmp_path: Path, kind: str, layer: int, frame: int, code: str
) -> None:
    source = image_fixture(tmp_path, kind)
    original = source.read_bytes()
    target = tmp_path / "rejected.aseprite"
    value = _snapshot({"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 255})
    exit_code, result = _compose(
        source,
        target,
        value,
        target={"layer": {"layer_path": [layer]}, "frame_number": frame},
    )
    assert exit_code != 0, result
    assert result["code"] == code
    assert source.read_bytes() == original
    assert not target.exists()


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


@pytest.mark.parametrize(
    "blend_mode", ["hue", "saturation", "color", "luminosity", "addition"]
)
def test_composite_refuses_grayscale_modes_with_different_native_meaning(
    tmp_path: Path, blend_mode: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    image_fixture(tmp_path, "grayscale")
    before = source.read_bytes()
    code, result = _compose(
        source,
        target,
        _snapshot({"kind": "grayscale", "gray": 90, "alpha": 128}, mode="grayscale"),
        blend_mode=blend_mode,
    )
    assert code != 0, result
    assert result["code"] == "paint_composite_unsupported"
    gap = result["details"]["gap"]
    assert blend_mode in gap["capability"]
    assert gap["aseprite_version"]
    assert gap["evidence"]
    validate(
        result,
        json.loads(spa("paint", "composite", "--schema").stdout)["failure_schema"],
    )
    assert source.read_bytes() == before
    assert not target.exists()


def test_composite_clips_a_fully_outside_position_without_native_integer_wrap(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _create(source)
    value = _snapshot({"kind": "rgba", "red": 1, "green": 2, "blue": 3, "alpha": 255})
    code, result = _compose(
        source, target, value, position={"x": 2**32, "y": 0}, clipping="clip"
    )
    assert code == 0, result
    assert result["pixels_changed"] == result["pixels_written"] == 0
    assert result["pixels_skipped_by_bounds"] == 1
    assert result["before_content_digest"] == result["after_content_digest"]


def test_composite_artifact_matches_inline_and_keeps_source(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    _create(source)
    original = source.read_bytes()
    value = _snapshot(
        {"kind": "rgba", "red": 130, "green": 20, "blue": 70, "alpha": 90}
    )
    artifact = tmp_path / "snapshot.json"
    artifact.write_text(json.dumps(value))
    code, inline = _compose(source, tmp_path / "inline.aseprite", value)
    assert code == 0, inline
    code, result = _compose(
        source,
        tmp_path / "artifact.aseprite",
        value,
        input={"kind": "artifact", "path": str(artifact)},
    )
    assert code == 0, result
    assert result["input_form"] == "artifact"
    assert result["after_content_digest"] == inline["after_content_digest"]
    assert result["applied_runs"] == inline["applied_runs"]
    assert source.read_bytes() == original
