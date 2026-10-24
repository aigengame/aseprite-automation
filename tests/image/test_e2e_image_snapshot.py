"""Canonical Image snapshots through the public CLI and real native files."""

import hashlib
import json
import os
from importlib.resources import files
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, render_frame, run, run_lua
from tests.support import (
    aseprite_chunks,
    inject_palette_change,
    process_diagnostics,
    snapshot_fixture,
    spa,
)

pytestmark = pytest.mark.e2e

FULL_AREA = {"x": 0, "y": 0, "width": 4, "height": 3}


def _individual(
    rectangle: dict | None = None, frame: int = 1, layer: dict | None = None
) -> dict:
    return {
        "kind": "individual",
        "target": {
            "layer": layer or {"layer_path": [1]},
            "frame_number": frame,
        },
        "rectangle": rectangle or FULL_AREA,
    }


def _replace_request(
    source: Path, destination: Path, value: dict, **options: object
) -> dict:
    """Return an Image Replace request of value for Layer 1, Frame 1.

    The request writes destination, not in place and without overwrite, from
    an inline snapshot. Each option replaces one field.
    """
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(destination),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "input": {"kind": "inline", "snapshot": value},
        **options,
    }


def _indexed_fixture(runtime: RuntimeObservation, tmp_path: Path, mode: str) -> Path:
    """Write `<mode>.aseprite` with `indexed_composite_scenarios.lua`."""
    return snapshot_fixture(
        runtime, tmp_path, mode, script="indexed_composite_scenarios.lua"
    )


def _get_request(sprite: Path, **options: object) -> dict:
    """Return an Image Get request of sprite.

    The default source is the individual Cel of Layer 1, Frame 1, in the
    rectangle at x 1, y 1 with width 2 and height 1. Each option replaces one
    field.
    """
    return {
        "sprite_file": str(sprite),
        "source": {
            "kind": "individual",
            "target": {
                "layer": {"layer_path": [1]},
                "frame_number": 1,
            },
            "rectangle": {"x": 1, "y": 1, "width": 2, "height": 1},
        },
        **options,
    }


def test_individual_get_reads_hidden_stored_pixels_and_rebases_roi(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = snapshot_fixture(runtime, tmp_path)
    original = source.read_bytes()

    result = expect_success("image get", _get_request(source))
    assert result["source"]["coordinate_space"] == "image-pixel"
    assert result["source"]["rectangle"] == {"x": 1, "y": 1, "width": 2, "height": 1}
    assert result["snapshot"] == {
        "coordinate_space": "image-pixel",
        "color_mode": "rgb",
        "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
        "rows": [
            [
                {
                    "length": 1,
                    "color": {
                        "kind": "rgba",
                        "red": 70,
                        "green": 80,
                        "blue": 90,
                        "alpha": 0,
                    },
                },
                {
                    "length": 1,
                    "color": {
                        "kind": "rgba",
                        "red": 3,
                        "green": 4,
                        "blue": 5,
                        "alpha": 128,
                    },
                },
            ]
        ],
    }
    assert result["source"]["layer_kind"] == "transparent"
    assert result["source"]["associated_cels"][0]["opacity"] == 0
    assert source.read_bytes() == original


@pytest.mark.parametrize("output_mode", ["preserve", "rgb"])
def test_composition_restores_preferences_and_visibility_on_success_and_failure(
    tmp_path: Path,
    runtime: RuntimeObservation,
    output_mode: str,
) -> None:
    output = tmp_path / "context.json"
    kernel = files("spa.kernel")
    lua = run_lua(
        Path(__file__).parent / "fixtures/composition_context.lua",
        runtime,
        out=output,
        layer_composition=kernel.joinpath("raster/image/layer_composition.lua"),
        effective_palette=kernel.joinpath("color/effective_palette.lua"),
        layer_select=kernel.joinpath("document/layer/layer_select.lua"),
        output_mode=output_mode,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    assert json.loads(output.read_text()) == {
        "success_restored": True,
        "failure_restored": True,
        "explicit_frame_and_roi": True,
    }


@pytest.mark.parametrize(
    ("mode", "output_mode"), [("tilemap", "preserve"), ("indexed-tilemap", "rgb")]
)
def test_native_tilemap_composition_does_not_expose_tile_indexes_as_colors(
    tmp_path: Path,
    runtime: RuntimeObservation,
    mode: str,
    output_mode: str,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    result = expect_success(
        "image get",
        _get_request(
            source,
            source=_composite(
                {"mode": "include", "layers": [{"layer_path": [1]}]},
                output_color_mode=output_mode,
            ),
        ),
    )
    assert result["snapshot"]["rows"][0][0]["color"] == {
        "kind": "rgba",
        "red": 250,
        "green": 0,
        "blue": 0,
        "alpha": 255,
    }
    outcome = run("image get", _get_request(source, source=_individual()))
    failure = outcome.envelope
    assert outcome.returncode == 2 and failure["code"] == "cel_unsupported_target"
    assert source.read_bytes() == original
    outcome = run(
        "image replace",
        _replace_request(source, tmp_path / "rejected.aseprite", result["snapshot"]),
    )
    failure = outcome.envelope
    assert outcome.returncode == 2 and failure["code"] == "cel_unsupported_target"


def test_replace_checks_every_linked_frame_palette_before_publication(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, "indexed-linked")
    before = expect_success("image get", _get_request(source, source=_individual()))
    inject_palette_change(source, [(0, 0, 0, 0), (255, 0, 0, 255)])
    assert (
        len(
            run("image get", _get_request(source, source=_individual())).envelope[
                "source"
            ]["associated_cels"]
        )
        == 2
    )
    original = source.read_bytes()
    value = before["snapshot"]
    value["rows"][0] = [{"length": 4, "color": {"kind": "palette-index", "index": 3}}]
    outcome = run(
        "image replace",
        _replace_request(source, source, value, in_place=True, overwrite=True),
    )
    failed = outcome.envelope
    assert outcome.returncode == 2 and failed["code"] == "image_snapshot_invalid", (
        failed
    )
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "mode", ["rgb-background", "grayscale-background", "indexed-background-alpha"]
)
def test_background_transparency_is_rejected_atomically(
    tmp_path: Path, runtime: RuntimeObservation, mode: str
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode)
    before = expect_success("image get", _get_request(source, source=_individual()))
    value = before["snapshot"]
    if mode.startswith("indexed"):
        value["rows"][0][0]["color"]["index"] = 3
    else:
        value["rows"][0][0]["color"]["alpha"] = 0
    original = source.read_bytes()
    outcome = run(
        "image replace",
        _replace_request(source, source, value, in_place=True, overwrite=True),
    )
    failure = outcome.envelope
    assert outcome.returncode == 2 and failure["code"] == "image_snapshot_invalid", (
        failure
    )
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "mode",
    ["rgb-background", "grayscale-background", "indexed-background", "reference"],
)
def test_replace_preserves_background_and_precise_reference_bounds(
    tmp_path: Path, runtime: RuntimeObservation, mode: str
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    before = expect_success("image get", _get_request(source, source=_individual()))
    assert before["source"]["layer_kind"] == (
        "reference" if mode == "reference" else "background"
    )
    value = before["snapshot"]
    color = (
        {"kind": "palette-index", "index": 0}
        if mode.startswith("indexed")
        else {"kind": "grayscale", "gray": 99, "alpha": 255}
        if mode.startswith("grayscale")
        else {"kind": "rgba", "red": 99, "green": 100, "blue": 101, "alpha": 255}
    )
    value["rows"][0] = [{"length": 4, "color": color}]
    target = tmp_path / "replaced.aseprite"
    expect_success("image replace", _replace_request(source, target, value))
    after = expect_success("image get", _get_request(target, source=_individual()))
    assert after["snapshot"] == value
    assert after["source"] == before["source"]
    assert source.read_bytes() == original
    if mode == "reference":
        old_extra = [
            payload for _, kind, payload in aseprite_chunks(original) if kind == 0x2006
        ]
        new_extra = [
            payload
            for _, kind, payload in aseprite_chunks(target.read_bytes())
            if kind == 0x2006
        ]
        assert old_extra and old_extra == new_extra


@pytest.mark.parametrize(
    ("source_kind", "code"),
    [
        (
            _individual({"x": -1, "y": 0, "width": 1, "height": 1}),
            "image_rectangle_out_of_bounds",
        ),
        (
            _individual({"x": 3, "y": 0, "width": 2, "height": 1}),
            "image_rectangle_out_of_bounds",
        ),
        (_individual(frame=99), "cel_frame_out_of_bounds"),
        (_individual(layer={"layer_name": "missing"}), "layer_missing"),
    ],
)
def test_individual_rejections_leave_source_unchanged(
    tmp_path: Path, runtime: RuntimeObservation, source_kind: dict, code: str
) -> None:
    source = snapshot_fixture(runtime, tmp_path)
    original = source.read_bytes()
    outcome = run("image get", _get_request(source, source=source_kind))
    rejected = outcome.envelope
    assert outcome.returncode == 2, rejected
    assert rejected["code"] == code
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("mode", "colors", "mask"),
    [
        (
            "grayscale",
            [
                {"kind": "grayscale", "gray": 72, "alpha": 0},
                {"kind": "grayscale", "gray": 9, "alpha": 128},
            ],
            {"kind": "grayscale", "gray": 0, "alpha": 0},
        ),
        (
            "indexed",
            [
                {"kind": "palette-index", "index": 0},
                {"kind": "palette-index", "index": 2},
            ],
            {"kind": "palette-index", "index": 2},
        ),
    ],
)
def test_native_modes_preserve_stored_values_and_palette_basis(
    tmp_path: Path,
    runtime: RuntimeObservation,
    mode: str,
    colors: list[dict],
    mask: dict,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode)
    result = expect_success("image get", _get_request(source))
    assert result["snapshot"]["color_mode"] == mode
    assert [run["color"] for run in result["snapshot"]["rows"][0]] == colors
    assert result["mask_color"] == mask
    palettes = result["effective_palettes"]
    if mode == "indexed":
        assert palettes == [
            {
                "frame_number": 1,
                "palette_frame_number": 1,
                "palette_size": 4,
                "indexes": [
                    {
                        "index": 0,
                        "color": {"red": 30, "green": 40, "blue": 50, "alpha": 255},
                    },
                    {
                        "index": 2,
                        "color": {"red": 0, "green": 0, "blue": 250, "alpha": 255},
                    },
                ],
            }
        ]
    else:
        assert palettes == []


@pytest.mark.parametrize(
    "mode", ["rgb", "grayscale", "indexed", "linked", "default-group"]
)
def test_replace_roundtrips_exact_pixels_and_preserves_linked_geometry(
    tmp_path: Path, runtime: RuntimeObservation, mode: str
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    before = expect_success("image get", _get_request(source, source=_individual()))
    value = before["snapshot"]
    color = (
        {"kind": "grayscale", "gray": 201, "alpha": 0}
        if mode == "grayscale"
        else {"kind": "palette-index", "index": 3}
        if mode == "indexed"
        else {"kind": "rgba", "red": 201, "green": 202, "blue": 203, "alpha": 0}
    )
    value["rows"][0] = [{"length": 4, "color": color}]
    target = tmp_path / "replaced.aseprite"

    result = expect_success("image replace", _replace_request(source, target, value))
    assert result["input_form"] == "inline"
    assert result["geometry_unchanged"] is True
    assert result["native_sharing_preserved"] is True
    assert result["persisted_reopen_verified"] is True
    assert result["before_content_digest"] != result["after_content_digest"]
    assert result["affected_cels"] == before["source"]["associated_cels"]
    assert source.read_bytes() == original
    for frame in [1, 2] if mode == "linked" else [1]:
        reopened = expect_success(
            "image get", _get_request(target, source=_individual(frame=frame))
        )
        assert reopened["snapshot"] == value
        assert (
            reopened["source"]["associated_cels"] == before["source"]["associated_cels"]
        )


def test_complete_json_artifact_roundtrip_above_inline_limit(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = snapshot_fixture(runtime, tmp_path, "large")
    area = {"x": 0, "y": 0, "width": 65, "height": 65}
    artifact = tmp_path / "snapshot.json"
    result = expect_success(
        "image get",
        _get_request(
            source,
            source=_individual(area),
            snapshot_destination={"path": str(artifact), "if_exists": "fail"},
        ),
    )
    assert result["output_form"] == "artifact"
    assert result["snapshot"] is None
    value = json.loads(artifact.read_text())
    assert value["rectangle"] == area
    assert len(value["rows"]) == 65
    target = tmp_path / "replaced.aseprite"
    replaced = expect_success(
        "image replace",
        _replace_request(
            source, target, {}, input={"kind": "artifact", "path": str(artifact)}
        ),
    )
    assert replaced["input_form"] == "artifact"
    assert replaced["before_content_digest"] == replaced["after_content_digest"]
    saved = tmp_path / "reopened.json"
    expect_success(
        "image get",
        _get_request(
            target,
            source=_individual(area),
            snapshot_destination={"path": str(saved), "if_exists": "fail"},
        ),
    )
    assert json.loads(saved.read_text()) == value


def _composite(composition: dict, **options: object) -> dict:
    return {
        "kind": "composite",
        "output_color_mode": "preserve",
        "frame_number": 1,
        "rectangle": {"x": 1, "y": 1, "width": 2, "height": 1},
        "layer_composition": composition,
        **options,
    }


def _indexed_first_row_indexes(snapshot: dict) -> list[int]:
    return [
        run["color"]["index"]
        for run in snapshot["rows"][0]
        for _ in range(run["length"])
    ]


def test_explicit_rgb_composite_keeps_indexed_source_and_transparency(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, "indexed-composite")
    original = source.read_bytes()
    result = expect_success(
        "image get",
        _get_request(
            source, source=_composite({"mode": "visible"}, output_color_mode="rgb")
        ),
    )
    assert result["color_mode"] == result["snapshot"]["color_mode"] == "rgb"
    assert result["source"]["color_mode"] == "indexed"
    assert result["source"]["mask_color"] == {"kind": "palette-index", "index": 2}
    assert result["snapshot"]["rows"] == [
        [
            {
                "length": 1,
                "color": {
                    "kind": "rgba",
                    "red": 30,
                    "green": 40,
                    "blue": 50,
                    "alpha": 255,
                },
            },
            {
                "length": 1,
                "color": {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 0},
            },
        ]
    ]
    assert result["mask_color"] == {
        "kind": "rgba",
        "red": 0,
        "green": 0,
        "blue": 0,
        "alpha": 0,
    }
    assert result["effective_palettes"] == [
        {"frame_number": 1, "palette_frame_number": 1, "palette_size": 4, "indexes": []}
    ]
    assert source.read_bytes() == original


@pytest.mark.parametrize("artifact", [False, True])
def test_preserve_indexed_composite_keeps_opaque_zero_and_nonzero_mask(
    tmp_path: Path,
    runtime: RuntimeObservation,
    artifact: bool,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, "indexed-composite")
    original = source.read_bytes()
    destination = tmp_path / "pixels.json"
    result = expect_success(
        "image get",
        _get_request(
            source,
            source=_composite(
                {"mode": "visible"},
                rectangle={"x": 1, "y": 1, "width": 2, "height": 1},
            ),
            **(
                {
                    "snapshot_destination": {
                        "path": str(destination),
                        "if_exists": "fail",
                    }
                }
                if artifact
                else {}
            ),
        ),
    )
    assert result["color_mode"] == "indexed"
    assert result["mask_color"] == {"kind": "palette-index", "index": 2}
    value = json.loads(destination.read_text()) if artifact else result["snapshot"]
    assert result["output_form"] == ("artifact" if artifact else "inline")
    assert value["rows"] == [
        [
            {"length": 1, "color": {"kind": "palette-index", "index": 0}},
            {"length": 1, "color": {"kind": "palette-index", "index": 2}},
        ]
    ]
    assert source.read_bytes() == original


@pytest.mark.parametrize(("mode", "mask"), [("plain-7", 7), ("plain-255", 255)])
def test_preserve_indexed_composite_handles_boundary_transparent_indexes(
    tmp_path: Path, runtime: RuntimeObservation, mode: str, mask: int
) -> None:
    source = _indexed_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    result = expect_success(
        "image get",
        _get_request(
            source,
            source=_composite(
                {"mode": "visible"},
                rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
            ),
        ),
    )
    assert result["mask_color"] == {"kind": "palette-index", "index": mask}
    assert _indexed_first_row_indexes(result["snapshot"]) == [0, mask, 3]
    assert source.read_bytes() == original


@pytest.mark.parametrize("artifact", [False, True])
def test_preserve_indexed_composite_rejects_missing_transparent_palette_entry(
    tmp_path: Path, runtime: RuntimeObservation, artifact: bool
) -> None:
    source = _indexed_fixture(runtime, tmp_path, "missing-mask")
    original = source.read_bytes()
    destination = tmp_path / "pixels.json"
    if artifact:
        destination.write_bytes(b"existing artifact")
    outcome = run(
        "image get",
        _get_request(
            source,
            source=_composite(
                {"mode": "visible"},
                rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
            ),
            **(
                {
                    "snapshot_destination": {
                        "path": str(destination),
                        "if_exists": "replace",
                    }
                }
                if artifact
                else {}
            ),
        ),
    )
    failure = outcome.envelope
    assert (
        outcome.returncode == 2 and failure["code"] == "image_composition_unsupported"
    ), failure
    assert "Transparent Color Index" in failure["details"]["reason"]
    assert source.read_bytes() == original
    if artifact:
        assert destination.read_bytes() == b"existing artifact"
    else:
        assert not destination.exists()


def test_preserve_indexed_composite_respects_hidden_groups_and_exact_include(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = _indexed_fixture(runtime, tmp_path, "hidden-group")
    original = source.read_bytes()
    for composition, expected in (
        ({"mode": "visible"}, [7, 7, 7]),
        ({"mode": "include", "layers": [{"layer_path": [1]}]}, [0, 7, 3]),
    ):
        result = expect_success(
            "image get",
            _get_request(
                source,
                source=_composite(
                    composition, rectangle={"x": 0, "y": 0, "width": 3, "height": 1}
                ),
            ),
        )
        assert _indexed_first_row_indexes(result["snapshot"]) == expected
        assert source.read_bytes() == original


def test_preserve_indexed_composite_uses_each_linked_frames_effective_palette(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = _indexed_fixture(runtime, tmp_path, "linked-frames")
    inject_palette_change(
        source,
        [
            (70, 80, 90, 255),
            (0, 0, 0, 255),
            (0, 0, 0, 255),
            (20, 210, 30, 255),
            (0, 0, 0, 255),
            (0, 0, 0, 255),
            (0, 0, 0, 255),
            (0, 0, 200, 255),
        ],
    )
    original = source.read_bytes()
    link = expect_success(
        "cel get",
        {
            "sprite_file": str(source),
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        },
    )
    assert link["cel"]["linked_cels"] == [{"layer_path": [1], "frame_number": 2}]
    for frame, red in ((1, 250), (2, 20)):
        result = expect_success(
            "image get",
            _get_request(
                source,
                source=_composite(
                    {"mode": "visible"},
                    frame_number=frame,
                    rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
                ),
            ),
        )
        assert _indexed_first_row_indexes(result["snapshot"]) == [0, 7, 3]
        palette = result["effective_palettes"][0]
        assert palette["palette_frame_number"] == frame
        assert palette["indexes"][1] == {
            "index": 3,
            "color": {
                "red": red,
                "green": 0 if frame == 1 else 210,
                "blue": 0 if frame == 1 else 30,
                "alpha": 255,
            },
        }
        assert source.read_bytes() == original


def test_preserve_indexed_composite_checks_only_requested_frames_palette(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = _indexed_fixture(runtime, tmp_path, "short-earlier-palette")
    inject_palette_change(
        source,
        [(20, 30, 40, 255)] * 7 + [(0, 0, 200, 255)],
    )
    original = source.read_bytes()
    result = expect_success(
        "image get",
        _get_request(
            source,
            source=_composite(
                {"mode": "visible"},
                frame_number=2,
                rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
            ),
        ),
    )
    assert result["effective_palettes"][0]["palette_frame_number"] == 2
    assert _indexed_first_row_indexes(result["snapshot"]) == [0, 7, 3]
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("mode", "composition", "expected"),
    [
        ("background-visible", {"mode": "visible"}, [0, 7, 3]),
        ("background-hidden", {"mode": "visible"}, [7, 7, 7]),
        (
            "background-hidden",
            {"mode": "include", "layers": [{"layer_path": [1]}]},
            [0, 7, 3],
        ),
    ],
)
def test_preserve_indexed_composite_keeps_background_and_visibility(
    tmp_path: Path,
    runtime: RuntimeObservation,
    mode: str,
    composition: dict,
    expected: list[int],
) -> None:
    source = _indexed_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    selected = expect_success(
        "layer get", {"sprite_file": str(source), "target": {"layer_path": [1]}}
    )
    assert selected["layer"]["is_background"] is True
    result = expect_success(
        "image get",
        _get_request(
            source,
            source=_composite(
                composition, rectangle={"x": 0, "y": 0, "width": 3, "height": 1}
            ),
        ),
    )
    assert _indexed_first_row_indexes(result["snapshot"]) == expected
    assert source.read_bytes() == original


def test_preserve_indexed_composite_renders_tile_pixels_without_changing_tile_ids(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = _indexed_fixture(runtime, tmp_path, "tilemap")
    original = source.read_bytes()
    selected = expect_success(
        "layer get", {"sprite_file": str(source), "target": {"layer_path": [1]}}
    )
    assert selected["layer"]["is_tilemap"] is True
    result = expect_success(
        "image get",
        _get_request(
            source,
            source=_composite(
                {"mode": "visible"},
                rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
            ),
        ),
    )
    assert _indexed_first_row_indexes(result["snapshot"]) == [0, 7, 3]
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (
            "indexed-opacity",
            [(150, 150, 75, 255), (100, 200, 100, 255), (90, 180, 135, 255)],
        ),
        (
            "indexed-blend",
            [(78, 78, 20, 255), (100, 200, 100, 255), (62, 147, 97, 255)],
        ),
    ],
)
def test_indexed_rgb_observation_uses_group_and_palette_alpha(
    tmp_path: Path,
    runtime: RuntimeObservation,
    mode: str,
    expected: list[tuple[int, int, int, int]],
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    result = expect_success(
        "image get",
        _get_request(
            source,
            source=_composite(
                {"mode": "visible"},
                output_color_mode="rgb",
                rectangle={"x": 1, "y": 1, "width": 3, "height": 1},
            ),
        ),
    )
    assert [
        tuple(run["color"][channel] for channel in ("red", "green", "blue", "alpha"))
        for run in result["snapshot"]["rows"][0]
    ] == expected
    assert source.read_bytes() == original


def test_rgb_composite_uses_requested_frame_palette_and_cannot_replace_indexes(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, "indexed-palette")
    inject_palette_change(
        source, [(70, 80, 90, 255), (8, 9, 10, 255), (1, 2, 3, 255), (5, 6, 7, 255)]
    )
    # Linked pixels are identical; only the requested Frame's Palette changes.
    original = source.read_bytes()
    values = []
    for frame in (1, 2):
        result = expect_success(
            "image get",
            _get_request(
                source,
                source=_composite(
                    {"mode": "visible"},
                    output_color_mode="rgb",
                    frame_number=frame,
                    rectangle=FULL_AREA,
                ),
            ),
        )
        assert result["effective_palettes"][0]["palette_frame_number"] == frame
        # Row 1 is the unchanged source index 1, interpreted with each Frame's Palette.
        values.append(result["snapshot"]["rows"][0][0]["color"])
    assert values == [
        {"kind": "rgba", "red": 250, "green": 0, "blue": 0, "alpha": 255},
        {"kind": "rgba", "red": 8, "green": 9, "blue": 10, "alpha": 255},
    ]
    destination = tmp_path / "rejected.aseprite"
    outcome = run(
        "image replace", _replace_request(source, destination, result["snapshot"])
    )
    failure = outcome.envelope
    assert outcome.returncode == 2 and failure["code"] == "image_snapshot_invalid", (
        failure
    )
    assert not destination.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("composition", "colors"),
    [
        ({"mode": "visible"}, [(0, 0, 255, 255), (0, 0, 0, 0)]),
        (
            {"mode": "include", "layers": [{"layer_name": "Ink"}]},
            [(255, 0, 0, 64), (0, 0, 0, 0)],
        ),
        (
            {
                "mode": "include",
                "layers": [{"layer_name": "Character"}, {"layer_name": "Ink"}],
            },
            [(255, 0, 0, 64), (0, 255, 0, 128)],
        ),
    ],
)
def test_native_composition_preserves_hidden_ancestry_and_rebases_canvas_roi(
    tmp_path: Path,
    runtime: RuntimeObservation,
    composition: dict,
    colors: list[tuple],
) -> None:
    source = snapshot_fixture(runtime, tmp_path, "composition")
    original = source.read_bytes()
    result = expect_success(
        "image get", _get_request(source, source=_composite(composition))
    )
    assert result["source"]["coordinate_space"] == "canvas-pixel"
    assert result["source"]["frame_number"] == 1
    observed = result["source"]["layer_composition"]
    if "layers" in observed:
        observed["layers"] = [
            {k: v for k, v in layer.items() if v is not None}
            for layer in observed["layers"]
        ]
    assert observed == composition
    assert result["source"]["compose_groups"] is True
    assert result["snapshot"]["rectangle"] == {"x": 0, "y": 0, "width": 2, "height": 1}
    runs = result["snapshot"]["rows"][0]
    assert [
        tuple(run["color"][key] for key in ("red", "green", "blue", "alpha"))
        for run in runs
    ] == colors
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("mode", "composition", "options", "expected"),
    [
        (
            "rgb",
            {"mode": "include", "layers": [{"layer_path": [9]}]},
            {},
            "layer_invalid_path",
        ),
        (
            "duplicate",
            {"mode": "include", "layers": [{"layer_name": "Stored"}]},
            {},
            "layer_ambiguous",
        ),
        ("rgb", {"mode": "visible"}, {"frame_number": 4}, "cel_frame_out_of_bounds"),
        (
            "rgb",
            {"mode": "visible"},
            {"rectangle": {"x": -1, "y": 0, "width": 2, "height": 1}},
            "image_rectangle_out_of_bounds",
        ),
        (
            "rgb",
            {"mode": "visible"},
            {"rectangle": {"x": 3, "y": 2, "width": 2, "height": 1}},
            "image_rectangle_out_of_bounds",
        ),
    ],
)
def test_composite_rejections_do_not_publish_partial_artifacts(
    tmp_path: Path,
    runtime: RuntimeObservation,
    mode: str,
    composition: dict,
    options: dict,
    expected: str,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    destination = tmp_path / "pixels.json"
    outcome = run(
        "image get",
        _get_request(
            source,
            source=_composite(composition, **options),
            snapshot_destination={"path": str(destination), "if_exists": "fail"},
        ),
    )
    rejected = outcome.envelope
    assert outcome.returncode == 2 and rejected["code"] == expected, rejected
    assert source.read_bytes() == original
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize(
    ("mode", "address", "expected"),
    [
        ("absent", {"layer": {"layer_path": [1]}, "frame_number": 2}, "cel_not_found"),
        (
            "composition",
            {"layer": {"layer_name": "Character"}, "frame_number": 1},
            "cel_unsupported_target",
        ),
    ],
)
def test_non_cel_targets_are_rejected(
    tmp_path: Path, runtime: RuntimeObservation, mode: str, address: dict, expected: str
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode)
    original = source.read_bytes()
    outcome = run(
        "image get",
        _get_request(
            source,
            source={"kind": "individual", "target": address, "rectangle": FULL_AREA},
        ),
    )
    rejected = outcome.envelope
    assert outcome.returncode == 2 and rejected["code"] == expected, rejected
    value = {
        "coordinate_space": "image-pixel",
        "color_mode": "indexed",
        "rectangle": FULL_AREA,
        "rows": [[{"length": 4, "color": {"kind": "palette-index", "index": 1}}]] * 3,
    }
    outcome = run(
        "image replace",
        _replace_request(
            source, source, value, target=address, in_place=True, overwrite=True
        ),
    )
    rejected = outcome.envelope
    assert outcome.returncode == 2 and rejected["code"] == expected, rejected
    assert source.read_bytes() == original


@pytest.mark.parametrize("defect", ["dimensions", "mode", "incomplete", "color"])
def test_invalid_replacement_artifacts_leave_existing_target_unchanged(
    tmp_path: Path, runtime: RuntimeObservation, defect: str
) -> None:
    source = snapshot_fixture(runtime, tmp_path)
    before = expect_success("image get", _get_request(source, source=_individual()))
    value = before["snapshot"]
    if defect == "dimensions":
        value["rectangle"]["height"] = 2
        value["rows"] = value["rows"][:2]
    elif defect == "mode":
        value["color_mode"] = "indexed"
        value["rows"] = [
            [{"length": 4, "color": {"kind": "palette-index", "index": 1}}]
        ] * 3
    elif defect == "incomplete":
        value["rows"].pop()
    else:
        value["rows"][0][0]["color"]["red"] = 256
    artifact = tmp_path / "pixels.json"
    artifact.write_text(json.dumps(value))
    target = tmp_path / "existing.aseprite"
    target.write_bytes(source.read_bytes())
    original = source.read_bytes()
    outcome = run(
        "image replace",
        _replace_request(
            source,
            target,
            {},
            overwrite=True,
            input={"kind": "artifact", "path": str(artifact)},
        ),
    )
    rejected = outcome.envelope
    assert outcome.returncode == 2 and rejected["code"] == "image_snapshot_invalid", (
        rejected
    )
    assert source.read_bytes() == original == target.read_bytes()
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "existing.aseprite",
        "pixels.json",
        "rgb.aseprite",
    ]


@pytest.mark.parametrize("mode", ["composition", "blend"])
@pytest.mark.parametrize("in_place", [False, True])
def test_replace_rejects_native_batch_group_metadata_loss_before_commit(
    tmp_path: Path,
    runtime: RuntimeObservation,
    mode: str,
    in_place: bool,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode)
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(source.read_bytes())
    original = source.read_bytes()
    before = expect_success("image get", _get_request(source, source=_individual()))
    outcome = run(
        "image replace",
        _replace_request(
            source, target, before["snapshot"], in_place=in_place, overwrite=True
        ),
    )
    rejected = outcome.envelope
    assert outcome.returncode == 1 and rejected["code"] == "kernel_execution_failed", (
        rejected
    )
    assert "Image Replace" in json.dumps(rejected)
    assert source.read_bytes() == original == target.read_bytes()
    assert set(tmp_path.iterdir()) == {source, target}


def test_hidden_pixel_difference_is_observable_even_when_exported_pngs_match(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = snapshot_fixture(runtime, tmp_path)
    target = tmp_path / "changed.aseprite"
    before = expect_success("image get", _get_request(source, source=_individual()))
    value = before["snapshot"]
    value["rows"][0] = [
        {
            "length": 4,
            "color": {"kind": "rgba", "red": 99, "green": 88, "blue": 77, "alpha": 0},
        }
    ]
    result = expect_success("image replace", _replace_request(source, target, value))
    assert render_frame(source, 1).tobytes() == render_frame(target, 1).tobytes()
    outcome = run("image get", _get_request(target, source=_individual()))
    after = outcome.envelope
    assert outcome.returncode == 0 and after["snapshot"] == value, after
    assert result["before_content_digest"] != result["after_content_digest"]


def test_paint_shared_color_conversion_preserves_nontrivial_index(
    tmp_path: Path,
    runtime: RuntimeObservation,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, "indexed")
    target = tmp_path / "painted.aseprite"
    painted = spa(
        "paint",
        "apply",
        "--input-json",
        json.dumps(
            {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": False,
                "overwrite": False,
                "target": {"layer_path": [1], "frame_number": 1},
                "clipping": "reject",
                "patch": {
                    "coordinate_space": "image-pixel",
                    "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                    "runs": [
                        {
                            "x": 0,
                            "y": 0,
                            "length": 1,
                            "color": {"kind": "palette-index", "index": 3},
                        }
                    ],
                },
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert painted.returncode == 0, painted.stdout
    outcome = run(
        "image get",
        _get_request(
            target, source=_individual({"x": 0, "y": 0, "width": 1, "height": 1})
        ),
    )
    result = outcome.envelope
    assert outcome.returncode == 0 and result["snapshot"]["rows"] == [
        [{"length": 1, "color": {"kind": "palette-index", "index": 3}}]
    ], result


def test_composite_preserves_native_group_blend_mode(
    tmp_path: Path, runtime: RuntimeObservation
) -> None:
    source = snapshot_fixture(runtime, tmp_path, "blend")
    original = source.read_bytes()
    result = expect_success(
        "image get", _get_request(source, source=_composite({"mode": "visible"}))
    )
    assert result["snapshot"]["rows"] == [
        [
            {
                "length": 2,
                "color": {
                    "kind": "rgba",
                    "red": 100,
                    "green": 78,
                    "blue": 50,
                    "alpha": 255,
                },
            }
        ]
    ]
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("mode", "output_mode", "expected"),
    [
        (
            "grayscale",
            "preserve",
            [
                {"kind": "grayscale", "gray": 72, "alpha": 0},
                {"kind": "grayscale", "gray": 9, "alpha": 128},
            ],
        ),
        (
            "indexed-zero",
            "preserve",
            [
                {"kind": "palette-index", "index": 0},
                {"kind": "palette-index", "index": 2},
            ],
        ),
        (
            "indexed",
            "rgb",
            [
                {"kind": "rgba", "red": 30, "green": 40, "blue": 50, "alpha": 255},
                {"kind": "rgba", "red": 0, "green": 0, "blue": 0, "alpha": 0},
            ],
        ),
        (
            "grayscale",
            "rgb",
            [
                {"kind": "rgba", "red": 72, "green": 72, "blue": 72, "alpha": 0},
                {"kind": "rgba", "red": 9, "green": 9, "blue": 9, "alpha": 128},
            ],
        ),
    ],
)
def test_native_composite_modes_share_the_same_artifact_value(
    tmp_path: Path,
    runtime: RuntimeObservation,
    mode: str,
    output_mode: str,
    expected: list,
) -> None:
    source = snapshot_fixture(runtime, tmp_path, mode + "-composite")
    original = source.read_bytes()
    request = _composite({"mode": "visible"}, output_color_mode=output_mode)
    inline = expect_success("image get", _get_request(source, source=request))
    assert [run["color"] for run in inline["snapshot"]["rows"][0]] == expected
    artifact = tmp_path / "pixels.json"
    result = expect_success(
        "image get",
        _get_request(
            source,
            source=request,
            snapshot_destination={"path": str(artifact), "if_exists": "fail"},
        ),
    )
    raw = artifact.read_bytes()
    assert json.loads(raw) == inline["snapshot"]
    assert result["snapshot"] is None and result["output_form"] == "artifact"
    assert result["artifact"] == {
        "role": "pixel-region-snapshot",
        "media_type": "application/json",
        "format": "json",
        "path": str(artifact),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    assert result["effective_palettes"] == inline["effective_palettes"]
    assert result["mask_color"] == inline["mask_color"]
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".*.staged.json"))
