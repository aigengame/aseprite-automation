"""Native Snapshot composition through the installed SPA public boundary."""

import json
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run
from tests.paint.support import create_sprite
from tests.support import image_fixture, spa

pytestmark = pytest.mark.e2e


def _snapshot(color: dict, width: int = 1, mode: str = "rgb") -> dict:
    return {
        "coordinate_space": "image-pixel",
        "color_mode": mode,
        "rectangle": {"x": 0, "y": 0, "width": width, "height": 1},
        "rows": [[{"length": width, "color": color}]],
    }


def _compose(
    source_file: Path, target_file: Path, value: dict, **options: object
) -> dict:
    """Return a `paint composite` request for the inline Snapshot value.

    The request writes a new target with Normal blend at full opacity, at (1, 1) on
    Layer 1, Frame 1. The options replace these fields.
    """
    return {
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
    }


def test_composite_persists_native_alpha_at_declared_image_position(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    create_sprite(source, width=3, height=2)
    original = source.read_bytes()
    color = {"kind": "rgba", "red": 240, "green": 80, "blue": 20, "alpha": 128}
    value = _snapshot(color)

    result = expect_success("paint composite", _compose(source, target, value))

    schema = json.loads(spa("paint", "composite", "--schema").stdout)
    validate(result, schema["result_schema"])
    assert result["pixels_changed"] == result["pixels_written"] == 1
    assert result["persisted_reopen_verified"] is True
    assert result["geometry_unchanged"] is True
    assert source.read_bytes() == original

    reopened = expect_success(
        "image get",
        {
            "sprite_file": str(target),
            "source": {
                "kind": "individual",
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                "rectangle": {"x": 1, "y": 1, "width": 1, "height": 1},
            },
        },
    )
    assert reopened["snapshot"] == value


@pytest.mark.parametrize("case", ["bounds", "color-mode"])
def test_invalid_composite_preserves_source_and_existing_target(
    tmp_path: Path, case: str
) -> None:
    # The Kernel refuses these rows: only the Sprite gives its bounds and Color Mode.
    # tests/paint/test_integration_composite.py has the refusals before the probe.
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    create_sprite(source, width=3, height=2)
    original = source.read_bytes()
    target.write_bytes(b"existing target")
    value = _snapshot({"kind": "rgba", "red": 1, "green": 2, "blue": 3, "alpha": 255})
    options: dict = {"overwrite": True}
    if case == "bounds":
        options["position"] = {"x": -1, "y": 0}
    else:
        value = _snapshot(
            {"kind": "grayscale", "gray": 90, "alpha": 128}, mode="grayscale"
        )
    outcome = run("paint composite", _compose(source, target, value, **options))
    result = outcome.envelope
    assert outcome.returncode != 0, result
    assert result["code"] == "paint_composite_invalid"
    assert source.read_bytes() == original
    assert target.read_bytes() == b"existing target"
    assert {item.name for item in tmp_path.iterdir()} == {
        "source.aseprite",
        "target.aseprite",
    }


@pytest.mark.parametrize(
    "kind,layer,frame,code",
    [
        ("reference", 1, 1, "cel_unsupported_target"),
        ("tilemap", 2, 1, "cel_unsupported_target"),
        ("absent", 1, 2, "cel_not_found"),
    ],
)
def test_composite_rejects_unsupported_cel_targets(
    tmp_path: Path,
    runtime: RuntimeObservation,
    kind: str,
    layer: int,
    frame: int,
    code: str,
) -> None:
    source = image_fixture(runtime, tmp_path, kind)
    original = source.read_bytes()
    target = tmp_path / "rejected.aseprite"
    value = _snapshot({"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 255})
    outcome = run(
        "paint composite",
        _compose(
            source,
            target,
            value,
            target={"layer": {"layer_path": [layer]}, "frame_number": frame},
        ),
    )
    result = outcome.envelope
    assert outcome.returncode != 0, result
    assert result["code"] == code
    assert source.read_bytes() == original
    assert not target.exists()


def test_composite_partitions_clipping_and_explicit_selection(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    create_sprite(source, width=3, height=2)
    value = _snapshot(
        {"kind": "rgba", "red": 9, "green": 20, "blue": 30, "alpha": 255}, width=4
    )
    selected = {"kind": "all", "rectangle": {"x": 2, "y": 0, "width": 1, "height": 1}}

    result = expect_success(
        "paint composite",
        _compose(
            source,
            target,
            value,
            position={"x": 1, "y": 0},
            clipping="clip",
            selection=selected,
        ),
    )

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
    create_sprite(source, width=3, height=2)
    color = {"kind": "rgba", "red": 240, "green": 80, "blue": 20, "alpha": 128}
    expect_success(
        "paint composite", _compose(source, target, _snapshot(color), opacity=opacity)
    )
    pixels = expect_success(
        "image get",
        {
            "sprite_file": str(target),
            "source": {
                "kind": "individual",
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                "rectangle": {"x": 1, "y": 1, "width": 1, "height": 1},
            },
        },
    )
    # Native Normal retains source RGB over an alpha-zero backdrop even at opacity 0
    # (Aseprite blend_funcs.cpp rgba_blender_normal, alpha-zero branch).
    expected = {**color, "alpha": alpha}
    assert pixels["snapshot"]["rows"] == [[{"length": 1, "color": expected}]]


@pytest.mark.parametrize("x", [-(2**31), 2**31 - 1])
def test_composite_clips_a_fully_outside_position_at_native_integer_limits(
    tmp_path: Path, x: int
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    create_sprite(source, width=3, height=2)
    value = _snapshot(
        {"kind": "rgba", "red": 1, "green": 2, "blue": 3, "alpha": 255}, width=2
    )
    result = expect_success(
        "paint composite",
        _compose(source, target, value, position={"x": x, "y": 0}, clipping="clip"),
    )
    assert result["position"] == {"x": x, "y": 0}
    assert result["skipped_by_bounds_runs"] == [{"x": x, "y": 0, "length": 2}]
    assert result["pixels_changed"] == result["pixels_written"] == 0
    assert result["pixels_skipped_by_bounds"] == 2
    assert result["before_content_digest"] == result["after_content_digest"]


def test_composite_artifact_matches_inline_and_keeps_source(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    create_sprite(source, width=3, height=2)
    original = source.read_bytes()
    value = _snapshot(
        {"kind": "rgba", "red": 130, "green": 20, "blue": 70, "alpha": 90}
    )
    artifact = tmp_path / "snapshot.json"
    artifact.write_text(json.dumps(value))
    inline = expect_success(
        "paint composite", _compose(source, tmp_path / "inline.aseprite", value)
    )
    result = expect_success(
        "paint composite",
        _compose(
            source,
            tmp_path / "artifact.aseprite",
            value,
            input={"kind": "artifact", "path": str(artifact)},
        ),
    )
    assert result["input_form"] == "artifact"
    assert result["after_content_digest"] == inline["after_content_digest"]
    assert result["applied_runs"] == inline["applied_runs"]
    assert source.read_bytes() == original
