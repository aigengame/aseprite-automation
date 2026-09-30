"""Canonical Image snapshots through the public CLI and real native files."""

import json
import os
import struct
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
from tests.support import inject_palette_change, process_diagnostics, spa

pytestmark = pytest.mark.e2e

FULL_AREA = {"x": 0, "y": 0, "width": 4, "height": 3}


@pytest.mark.parametrize(
    "artifact_path", ["bad\u0000.json", "~spa-pr114-no-such-user/snapshot.json"]
)
def test_unusable_snapshot_artifact_path_returns_failure_without_commit(
    tmp_path: Path,
    artifact_path: str,
) -> None:
    source = _fixture(tmp_path)
    destination = tmp_path / "existing.aseprite"
    destination.write_bytes(source.read_bytes())
    original_source, original_target = source.read_bytes(), destination.read_bytes()
    run = spa(
        "image",
        "replace",
        "--input-json",
        "-",
        stdin=json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(destination),
                "in_place": False,
                "overwrite": True,
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                "input": {"kind": "artifact", "path": artifact_path},
            }
        ),
    )
    assert run.returncode != 0
    assert run.stdout, run.stderr
    failure = json.loads(run.stdout)
    schema = json.loads(spa("image", "replace", "--schema").stdout)
    validate(failure, schema["failure_schema"])
    assert failure["code"] == "artifact_file_failed", failure
    assert failure["details"]["reason"] == "input_file_unreadable"
    assert "Traceback" not in run.stderr
    assert source.read_bytes() == original_source
    assert destination.read_bytes() == original_target
    assert set(tmp_path.iterdir()) == {source, destination}


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


def _replace(
    source: Path, destination: Path, value: dict, **options: object
) -> tuple[int, dict]:
    run = spa(
        "image",
        "replace",
        "--input-json",
        json.dumps(
            {
                "source_sprite_file": str(source),
                "target_sprite_file": str(destination),
                "in_place": False,
                "overwrite": False,
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                "input": {"kind": "inline", "snapshot": value},
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                **options,
            }
        ),
    )
    return run.returncode, json.loads(run.stdout)


def _chunks(raw: bytes | bytearray):
    frame_at = 128
    while frame_at < len(raw):
        size = struct.unpack_from("<I", raw, frame_at)[0]
        at = frame_at + 16
        while at < frame_at + size:
            length, kind = struct.unpack_from("<IH", raw, at)
            yield at, kind, bytes(raw[at + 6 : at + length])
            at += length
        frame_at += size


def _fixture(
    tmp_path: Path, mode: str = "rgb", *, script: str = "snapshot_targets.lua"
) -> Path:
    source = tmp_path / f"{mode}.aseprite"
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    with tempfile.TemporaryDirectory(prefix="spa-snapshot-fixture-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={source}",
                "--script-param",
                f"mode={mode}",
                "--script",
                str(Path(__file__).parent / "fixtures" / script),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, process_diagnostics(run)
    if mode in {
        "composition",
        "blend",
        "indexed-blend",
        "indexed-opacity",
        "hidden-group",
    }:
        # Batch SaveAs omits group fields in 1.3.18.5. Supply independent native
        # file-format evidence, as with Palette Change fixtures, instead of
        # assuming a live Group opacity was serialized.
        raw = bytearray(source.read_bytes())
        flags = struct.unpack_from("<I", raw, 14)[0]
        struct.pack_into("<I", raw, 14, flags | 2)
        group_number = 0
        for at, kind, _ in _chunks(raw):
            if kind == 0x2004 and struct.unpack_from("<H", raw, at + 8)[0] == 1:
                group_number += 1
                raw[at + 18] = (
                    128
                    if mode in {"composition", "indexed-opacity", "hidden-group"}
                    and group_number == 1
                    else 192
                    if mode == "hidden-group" and group_number == 2
                    else 255
                )
                if mode in {"blend", "indexed-blend"} or (
                    mode == "hidden-group" and group_number == 1
                ):
                    struct.pack_into("<H", raw, at + 16, 1)  # native MULTIPLY
        source.write_bytes(raw)
    elif mode == "reference":
        raw = bytearray(source.read_bytes())
        for at, kind, _ in _chunks(raw):
            if kind == 0x2006:
                struct.pack_into("<4i", raw, at + 10, 32768, -81920, 950272, 475136)
        source.write_bytes(raw)
    return source


def _indexed_fixture(tmp_path: Path, mode: str) -> Path:
    return _fixture(tmp_path, mode, script="indexed_composite_scenarios.lua")


def _get(sprite: Path, **options: object) -> tuple[int, dict]:
    run = spa(
        "image",
        "get",
        "--input-json",
        json.dumps(
            {
                "sprite_file": str(sprite),
                "source": {
                    "kind": "individual",
                    "target": {
                        "layer": {"layer_path": [1]},
                        "frame_number": 1,
                    },
                    "rectangle": {"x": 1, "y": 1, "width": 2, "height": 1},
                },
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                **options,
            }
        ),
    )
    return run.returncode, json.loads(run.stdout)


def test_individual_get_reads_hidden_stored_pixels_and_rebases_roi(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path)
    original = source.read_bytes()

    code, result = _get(source)

    assert code == 0, result
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
    output_mode: str,
) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    output = tmp_path / "context.json"
    kernel = files("spa.kernel")
    with tempfile.TemporaryDirectory(prefix="spa-composition-context-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        args = [str(prepared.executable), "--batch"]
        for name, value in {
            "out": output,
            "layer_composition": kernel.joinpath("raster/image/layer_composition.lua"),
            "effective_palette": kernel.joinpath("color/effective_palette.lua"),
            "layer_select": kernel.joinpath("document/layer/layer_select.lua"),
            "output_mode": output_mode,
        }.items():
            args.extend(("--script-param", f"{name}={value}"))
        args.extend(
            (
                "--script",
                str(Path(__file__).parent / "fixtures/composition_context.lua"),
            )
        )
        run = subprocess.run(
            args, text=True, capture_output=True, check=False, env=prepared.environment
        )
    assert run.returncode == 0, process_diagnostics(run)
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
    mode: str,
    output_mode: str,
) -> None:
    source = _fixture(tmp_path, mode)
    original = source.read_bytes()
    code, result = _get(
        source,
        source=_composite(
            {"mode": "include", "layers": [{"layer_path": [1]}]},
            output_color_mode=output_mode,
        ),
    )
    assert code == 0, json.dumps(result)
    assert result["snapshot"]["rows"][0][0]["color"] == {
        "kind": "rgba",
        "red": 250,
        "green": 0,
        "blue": 0,
        "alpha": 255,
    }
    code, failure = _get(source, source=_individual())
    assert code == 2 and failure["code"] == "cel_unsupported_target"
    assert source.read_bytes() == original
    code, failure = _replace(source, tmp_path / "rejected.aseprite", result["snapshot"])
    assert code == 2 and failure["code"] == "cel_unsupported_target"


def test_replace_checks_every_linked_frame_palette_before_publication(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "indexed-linked")
    code, before = _get(source, source=_individual())
    assert code == 0, before
    inject_palette_change(source, [(0, 0, 0, 0), (255, 0, 0, 255)])
    assert len(_get(source, source=_individual())[1]["source"]["associated_cels"]) == 2
    original = source.read_bytes()
    value = before["snapshot"]
    value["rows"][0] = [{"length": 4, "color": {"kind": "palette-index", "index": 3}}]
    code, failed = _replace(source, source, value, in_place=True, overwrite=True)
    assert code == 2 and failed["code"] == "image_snapshot_invalid", failed
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "mode", ["rgb-background", "grayscale-background", "indexed-background-alpha"]
)
def test_background_transparency_is_rejected_atomically(
    tmp_path: Path, mode: str
) -> None:
    source = _fixture(tmp_path, mode)
    code, before = _get(source, source=_individual())
    assert code == 0, before
    value = before["snapshot"]
    if mode.startswith("indexed"):
        value["rows"][0][0]["color"]["index"] = 3
    else:
        value["rows"][0][0]["color"]["alpha"] = 0
    original = source.read_bytes()
    code, failure = _replace(source, source, value, in_place=True, overwrite=True)
    assert code == 2 and failure["code"] == "image_snapshot_invalid", failure
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "mode",
    ["rgb-background", "grayscale-background", "indexed-background", "reference"],
)
def test_replace_preserves_background_and_precise_reference_bounds(
    tmp_path: Path, mode: str
) -> None:
    source = _fixture(tmp_path, mode)
    original = source.read_bytes()
    code, before = _get(source, source=_individual())
    assert code == 0, json.dumps(before)
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
    code, result = _replace(source, target, value)
    assert code == 0, json.dumps(result)
    code, after = _get(target, source=_individual())
    assert code == 0, after
    assert after["snapshot"] == value
    assert after["source"] == before["source"]
    assert source.read_bytes() == original
    if mode == "reference":
        old_extra = [
            payload for _, kind, payload in _chunks(original) if kind == 0x2006
        ]
        new_extra = [
            payload
            for _, kind, payload in _chunks(target.read_bytes())
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
    tmp_path: Path, source_kind: dict, code: str
) -> None:
    source = _fixture(tmp_path)
    original = source.read_bytes()
    status, rejected = _get(source, source=source_kind)
    assert status == 2, rejected
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
    mode: str,
    colors: list[dict],
    mask: dict,
) -> None:
    source = _fixture(tmp_path, mode)
    code, result = _get(source)
    assert code == 0, result
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
    tmp_path: Path, mode: str
) -> None:
    source = _fixture(tmp_path, mode)
    original = source.read_bytes()
    code, before = _get(source, source=_individual())
    assert code == 0, before
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

    code, result = _replace(source, target, value)

    assert code == 0, result
    assert result["input_form"] == "inline"
    assert result["geometry_unchanged"] is True
    assert result["native_sharing_preserved"] is True
    assert result["persisted_reopen_verified"] is True
    assert result["before_content_digest"] != result["after_content_digest"]
    assert result["affected_cels"] == before["source"]["associated_cels"]
    assert source.read_bytes() == original
    for frame in [1, 2] if mode == "linked" else [1]:
        code, reopened = _get(target, source=_individual(frame=frame))
        assert code == 0, reopened
        assert reopened["snapshot"] == value
        assert (
            reopened["source"]["associated_cels"] == before["source"]["associated_cels"]
        )


def test_complete_json_artifact_roundtrip_above_inline_limit(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "large")
    area = {"x": 0, "y": 0, "width": 65, "height": 65}
    artifact = tmp_path / "snapshot.json"
    code, result = _get(
        source,
        source=_individual(area),
        snapshot_destination={"path": str(artifact), "if_exists": "fail"},
    )
    assert code == 0, result
    assert result["output_form"] == "artifact"
    assert result["snapshot"] is None
    value = json.loads(artifact.read_text())
    assert value["rectangle"] == area
    assert len(value["rows"]) == 65
    target = tmp_path / "replaced.aseprite"
    code, replaced = _replace(
        source, target, {}, input={"kind": "artifact", "path": str(artifact)}
    )
    assert code == 0, replaced
    assert replaced["input_form"] == "artifact"
    assert replaced["before_content_digest"] == replaced["after_content_digest"]
    saved = tmp_path / "reopened.json"
    code, reopened = _get(
        target,
        source=_individual(area),
        snapshot_destination={"path": str(saved), "if_exists": "fail"},
    )
    assert code == 0, reopened
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
) -> None:
    source = _fixture(tmp_path, "indexed-composite")
    original = source.read_bytes()
    code, result = _get(
        source,
        source=_composite({"mode": "visible"}, output_color_mode="rgb"),
    )
    assert code == 0, result
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
    artifact: bool,
) -> None:
    source = _fixture(tmp_path, "indexed-composite")
    original = source.read_bytes()
    destination = tmp_path / "pixels.json"
    code, result = _get(
        source,
        source=_composite(
            {"mode": "visible"},
            rectangle={"x": 1, "y": 1, "width": 2, "height": 1},
        ),
        **(
            {"snapshot_destination": {"path": str(destination), "if_exists": "fail"}}
            if artifact
            else {}
        ),
    )
    assert code == 0, result
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
    tmp_path: Path, mode: str, mask: int
) -> None:
    source = _indexed_fixture(tmp_path, mode)
    original = source.read_bytes()
    code, result = _get(
        source,
        source=_composite(
            {"mode": "visible"},
            rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
        ),
    )
    assert code == 0, result
    assert result["mask_color"] == {"kind": "palette-index", "index": mask}
    assert _indexed_first_row_indexes(result["snapshot"]) == [0, mask, 3]
    assert source.read_bytes() == original


@pytest.mark.parametrize("artifact", [False, True])
def test_preserve_indexed_composite_rejects_missing_transparent_palette_entry(
    tmp_path: Path, artifact: bool
) -> None:
    source = _indexed_fixture(tmp_path, "missing-mask")
    original = source.read_bytes()
    destination = tmp_path / "pixels.json"
    if artifact:
        destination.write_bytes(b"existing artifact")
    code, failure = _get(
        source,
        source=_composite(
            {"mode": "visible"},
            rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
        ),
        **(
            {"snapshot_destination": {"path": str(destination), "if_exists": "replace"}}
            if artifact
            else {}
        ),
    )
    assert code == 2 and failure["code"] == "image_composition_unsupported", failure
    assert "Transparent Color Index" in failure["details"]["reason"]
    assert source.read_bytes() == original
    if artifact:
        assert destination.read_bytes() == b"existing artifact"
    else:
        assert not destination.exists()


def test_preserve_indexed_composite_respects_hidden_groups_and_exact_include(
    tmp_path: Path,
) -> None:
    source = _indexed_fixture(tmp_path, "hidden-group")
    original = source.read_bytes()
    for composition, expected in (
        ({"mode": "visible"}, [7, 7, 7]),
        ({"mode": "include", "layers": [{"layer_path": [1]}]}, [0, 7, 3]),
    ):
        code, result = _get(
            source,
            source=_composite(
                composition, rectangle={"x": 0, "y": 0, "width": 3, "height": 1}
            ),
        )
        assert code == 0, result
        assert _indexed_first_row_indexes(result["snapshot"]) == expected
        assert source.read_bytes() == original


def test_preserve_indexed_composite_uses_each_linked_frames_effective_palette(
    tmp_path: Path,
) -> None:
    source = _indexed_fixture(tmp_path, "linked-frames")
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
    link = spa(
        "cel",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(source),
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            }
        ),
    )
    assert link.returncode == 0, link.stdout
    assert json.loads(link.stdout)["cel"]["linked_cels"] == [
        {"layer_path": [1], "frame_number": 2}
    ]
    for frame, red in ((1, 250), (2, 20)):
        code, result = _get(
            source,
            source=_composite(
                {"mode": "visible"},
                frame_number=frame,
                rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
            ),
        )
        assert code == 0, result
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
) -> None:
    source = _indexed_fixture(tmp_path, "short-earlier-palette")
    inject_palette_change(
        source,
        [(20, 30, 40, 255)] * 7 + [(0, 0, 200, 255)],
    )
    original = source.read_bytes()
    code, result = _get(
        source,
        source=_composite(
            {"mode": "visible"},
            frame_number=2,
            rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
        ),
    )
    assert code == 0, result
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
    tmp_path: Path, mode: str, composition: dict, expected: list[int]
) -> None:
    source = _indexed_fixture(tmp_path, mode)
    original = source.read_bytes()
    selected = spa(
        "layer",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(source),
                "target": {"layer_path": [1]},
            }
        ),
    )
    assert selected.returncode == 0, selected.stdout
    assert json.loads(selected.stdout)["layer"]["is_background"] is True
    code, result = _get(
        source,
        source=_composite(
            composition, rectangle={"x": 0, "y": 0, "width": 3, "height": 1}
        ),
    )
    assert code == 0, result
    assert _indexed_first_row_indexes(result["snapshot"]) == expected
    assert source.read_bytes() == original


def test_preserve_indexed_composite_renders_tile_pixels_without_changing_tile_ids(
    tmp_path: Path,
) -> None:
    source = _indexed_fixture(tmp_path, "tilemap")
    original = source.read_bytes()
    selected = spa(
        "layer",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(source),
                "target": {"layer_path": [1]},
            }
        ),
    )
    assert selected.returncode == 0, selected.stdout
    assert json.loads(selected.stdout)["layer"]["is_tilemap"] is True
    code, result = _get(
        source,
        source=_composite(
            {"mode": "visible"},
            rectangle={"x": 0, "y": 0, "width": 3, "height": 1},
        ),
    )
    assert code == 0, result
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
    mode: str,
    expected: list[tuple[int, int, int, int]],
) -> None:
    source = _fixture(tmp_path, mode)
    original = source.read_bytes()
    code, result = _get(
        source,
        source=_composite(
            {"mode": "visible"},
            output_color_mode="rgb",
            rectangle={"x": 1, "y": 1, "width": 3, "height": 1},
        ),
    )
    assert code == 0, result
    assert [
        tuple(run["color"][channel] for channel in ("red", "green", "blue", "alpha"))
        for run in result["snapshot"]["rows"][0]
    ] == expected
    assert source.read_bytes() == original


def test_rgb_composite_uses_requested_frame_palette_and_cannot_replace_indexes(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "indexed-palette")
    inject_palette_change(
        source, [(70, 80, 90, 255), (8, 9, 10, 255), (1, 2, 3, 255), (5, 6, 7, 255)]
    )
    # Linked pixels are identical; only the requested Frame's Palette changes.
    original = source.read_bytes()
    values = []
    for frame in (1, 2):
        code, result = _get(
            source,
            source=_composite(
                {"mode": "visible"},
                output_color_mode="rgb",
                frame_number=frame,
                rectangle=FULL_AREA,
            ),
        )
        assert code == 0, result
        assert result["effective_palettes"][0]["palette_frame_number"] == frame
        # Row 1 is the unchanged source index 1, interpreted with each Frame's Palette.
        values.append(result["snapshot"]["rows"][0][0]["color"])
    assert values == [
        {"kind": "rgba", "red": 250, "green": 0, "blue": 0, "alpha": 255},
        {"kind": "rgba", "red": 8, "green": 9, "blue": 10, "alpha": 255},
    ]
    destination = tmp_path / "rejected.aseprite"
    code, failure = _replace(source, destination, result["snapshot"])
    assert code == 2 and failure["code"] == "image_snapshot_invalid", failure
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
    composition: dict,
    colors: list[tuple],
) -> None:
    source = _fixture(tmp_path, "composition")
    original = source.read_bytes()
    code, result = _get(source, source=_composite(composition))
    assert code == 0, result
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
        ("rgb", {"mode": "include", "layers": []}, {}, "invalid_request"),
        ("rgb", {"mode": "all"}, {}, "invalid_request"),
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
    tmp_path: Path, mode: str, composition: dict, options: dict, expected: str
) -> None:
    source = _fixture(tmp_path, mode)
    original = source.read_bytes()
    destination = tmp_path / "pixels.json"
    code, rejected = _get(
        source,
        source=_composite(composition, **options),
        snapshot_destination={"path": str(destination), "if_exists": "fail"},
    )
    assert code == 2 and rejected["code"] == expected, rejected
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
    tmp_path: Path, mode: str, address: dict, expected: str
) -> None:
    source = _fixture(tmp_path, mode)
    original = source.read_bytes()
    code, rejected = _get(
        source, source={"kind": "individual", "target": address, "rectangle": FULL_AREA}
    )
    assert code == 2 and rejected["code"] == expected, rejected
    value = {
        "coordinate_space": "image-pixel",
        "color_mode": "indexed",
        "rectangle": FULL_AREA,
        "rows": [[{"length": 4, "color": {"kind": "palette-index", "index": 1}}]] * 3,
    }
    code, rejected = _replace(
        source, source, value, target=address, in_place=True, overwrite=True
    )
    assert code == 2 and rejected["code"] == expected, rejected
    assert source.read_bytes() == original


@pytest.mark.parametrize("defect", ["dimensions", "mode", "incomplete", "color"])
def test_invalid_replacement_artifacts_leave_existing_target_unchanged(
    tmp_path: Path, defect: str
) -> None:
    source = _fixture(tmp_path)
    code, before = _get(source, source=_individual())
    assert code == 0, before
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
    code, rejected = _replace(
        source,
        target,
        {},
        overwrite=True,
        input={"kind": "artifact", "path": str(artifact)},
    )
    assert code == 2 and rejected["code"] == "image_snapshot_invalid", rejected
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
    mode: str,
    in_place: bool,
) -> None:
    source = _fixture(tmp_path, mode)
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(source.read_bytes())
    original = source.read_bytes()
    code, before = _get(source, source=_individual())
    assert code == 0, before
    code, rejected = _replace(
        source, target, before["snapshot"], in_place=in_place, overwrite=True
    )
    assert code == 1 and rejected["code"] == "kernel_execution_failed", rejected
    assert "Image Replace" in json.dumps(rejected)
    assert source.read_bytes() == original == target.read_bytes()
    assert set(tmp_path.iterdir()) == {source, target}


def test_hidden_pixel_difference_is_observable_even_when_exported_pngs_match(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path)
    target = tmp_path / "changed.aseprite"
    code, before = _get(source, source=_individual())
    assert code == 0, before
    value = before["snapshot"]
    value["rows"][0] = [
        {
            "length": 4,
            "color": {"kind": "rgba", "red": 99, "green": 88, "blue": 77, "alpha": 0},
        }
    ]
    code, result = _replace(source, target, value)
    assert code == 0, result
    from PIL import Image

    images = []
    for sprite in [source, target]:
        path = sprite.with_suffix(".png")
        run = spa(
            "export",
            "image",
            "--input-json",
            json.dumps(
                {
                    "source_sprite_file": str(sprite),
                    "destination": {"path": str(path), "if_exists": "fail"},
                    "frame_number": 1,
                    "color_mode": "preserve",
                    "color_profile": "preserve",
                    "transparency": "preserve",
                    "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                }
            ),
        )
        assert run.returncode == 0, run.stdout
        with Image.open(path) as image:
            images.append(image.convert("RGBA").tobytes())
    assert images[0] == images[1]
    code, after = _get(target, source=_individual())
    assert code == 0 and after["snapshot"] == value, after
    assert result["before_content_digest"] != result["after_content_digest"]


def test_paint_shared_color_conversion_preserves_nontrivial_index(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "indexed")
    target = tmp_path / "painted.aseprite"
    run = spa(
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
    assert run.returncode == 0, run.stdout
    code, result = _get(
        target, source=_individual({"x": 0, "y": 0, "width": 1, "height": 1})
    )
    assert code == 0 and result["snapshot"]["rows"] == [
        [{"length": 1, "color": {"kind": "palette-index", "index": 3}}]
    ], result


def test_composite_preserves_native_group_blend_mode(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "blend")
    original = source.read_bytes()
    code, result = _get(source, source=_composite({"mode": "visible"}))
    assert code == 0, result
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
    tmp_path: Path, mode: str, output_mode: str, expected: list
) -> None:
    source = _fixture(tmp_path, mode + "-composite")
    request = _composite({"mode": "visible"}, output_color_mode=output_mode)
    code, inline = _get(source, source=request)
    assert code == 0, inline
    assert [run["color"] for run in inline["snapshot"]["rows"][0]] == expected
    artifact = tmp_path / "pixels.json"
    code, result = _get(
        source,
        source=request,
        snapshot_destination={"path": str(artifact), "if_exists": "fail"},
    )
    assert code == 0, result
    assert json.loads(artifact.read_text()) == inline["snapshot"]
    assert result["effective_palettes"] == inline["effective_palettes"]
    assert result["mask_color"] == inline["mask_color"]
