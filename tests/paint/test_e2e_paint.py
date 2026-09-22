"""Installed Paint Operations against a real Aseprite executable."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _fixture(target: Path, kind: str) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    fixture = Path(__file__).parent / "fixtures" / "paint_target.lua"
    with tempfile.TemporaryDirectory(prefix="spa-paint-fixture-") as work:
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
                f"kind={kind}",
                "--script-param",
                f"out={target}",
                "--script",
                str(fixture),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr
    assert target.is_file()


def _create(source: Path) -> None:
    run = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(
            {
                "target_sprite_file": str(source),
                "width": 3,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {"kind": "transparent"},
                "overwrite": False,
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert run.returncode == 0, run.stdout


def _apply(
    source: Path,
    target: Path,
    patch: dict[str, object],
    *,
    address: dict[str, object] | None = None,
    clipping: str = "reject",
    selection: dict[str, object] | None = None,
    in_place: bool = False,
    overwrite: bool = False,
) -> subprocess.CompletedProcess[str]:
    request: dict[str, object] = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": in_place,
        "overwrite": overwrite,
        "target": address or {"layer_path": [1], "frame_number": 1},
        "patch": patch,
        "clipping": clipping,
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }
    if selection is not None:
        request["selection"] = selection
    return spa("paint", "apply", "--input-json", json.dumps(request))


def _rgba_patch(
    *, x: int, y: int, length: int, width: int | None = None
) -> dict[str, object]:
    return {
        "coordinate_space": "image-pixel",
        "rectangle": {
            "x": x,
            "y": y,
            "width": length if width is None else width,
            "height": 1,
        },
        "runs": [
            {
                "x": x,
                "y": y,
                "length": length,
                "color": {
                    "kind": "rgba",
                    "red": 17,
                    "green": 34,
                    "blue": 51,
                    "alpha": 255,
                },
            }
        ],
    }


def test_apply_persists_and_reopens_one_rgb_pixel_patch(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _create(source)
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "target": {"layer_path": [1], "frame_number": 1},
        "patch": {
            "coordinate_space": "image-pixel",
            "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
            "runs": [
                {
                    "x": 0,
                    "y": 0,
                    "length": 2,
                    "color": {
                        "kind": "rgba",
                        "red": 17,
                        "green": 34,
                        "blue": 51,
                        "alpha": 255,
                    },
                }
            ],
        },
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
    }

    run = spa("paint", "apply", "--input-json", json.dumps(request))

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    schema = json.loads(spa("paint", "apply", "--schema").stdout)
    validate(result, schema["result_schema"])
    assert result["persisted_reopen_verified"] is True
    assert result["requested_rectangle"] == request["patch"]["rectangle"]
    assert result["applied_rectangle"] == request["patch"]["rectangle"]
    assert result["pixels_requested"] == 2
    assert result["pixels_written"] == 2
    assert result["pixels_changed"] == 2
    assert result["affected_cels"] == [
        {
            "layer_path": [1],
            "frame_number": 1,
            "position": {"x": 0, "y": 0},
            "bounds": {"x": 0, "y": 0, "width": 3, "height": 2},
            "linked_to_target": True,
        }
    ]
    assert result["linked_cels_preserved"] is True
    assert result["geometry_unchanged"] is True
    assert result["before_content_digest"] != result["after_content_digest"]
    assert target.is_file()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_digest


def test_reject_clipping_is_atomic_and_clip_reports_partial_and_empty_writes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    _create(source)
    source_bytes = source.read_bytes()

    rejected_target = tmp_path / "rejected.aseprite"
    rejected = _apply(source, rejected_target, _rgba_patch(x=-1, y=0, length=2))
    assert rejected.returncode == 1, rejected.stdout
    assert json.loads(rejected.stdout)["code"] == "kernel_execution_failed"
    assert not rejected_target.exists()
    assert source.read_bytes() == source_bytes

    clipped_target = tmp_path / "clipped.aseprite"
    clipped = _apply(
        source,
        clipped_target,
        _rgba_patch(x=-1, y=0, length=2),
        clipping="clip",
    )
    assert clipped.returncode == 0, clipped.stdout
    clipped_result = json.loads(clipped.stdout)
    assert clipped_result["applied_rectangle"] == {
        "x": 0,
        "y": 0,
        "width": 1,
        "height": 1,
    }
    assert clipped_result["pixels_written"] == 1
    assert clipped_result["pixels_skipped_by_bounds"] == 1
    assert clipped_result["skipped_by_bounds_runs"][0]["x"] == -1

    empty_target = tmp_path / "fully-clipped.aseprite"
    fully_clipped = _apply(
        source,
        empty_target,
        _rgba_patch(x=-2, y=0, length=1),
        clipping="clip",
    )
    assert fully_clipped.returncode == 0, fully_clipped.stdout
    empty_result = json.loads(fully_clipped.stdout)
    assert empty_result["applied_rectangle"]["width"] == 0
    assert empty_result["applied_rectangle"]["height"] == 0
    assert empty_result["pixels_written"] == 0
    assert empty_result["before_content_digest"] == empty_result["after_content_digest"]


def test_selection_maps_image_pixels_through_the_target_cel_position(
    tmp_path: Path,
) -> None:
    source = tmp_path / "offset-linked.aseprite"
    target = tmp_path / "selected.aseprite"
    _fixture(source, "linked-rgb")

    run = _apply(
        source,
        target,
        _rgba_patch(x=0, y=0, length=2),
        selection={
            "kind": "all",
            "rectangle": {"x": 2, "y": 0, "width": 1, "height": 1},
        },
    )

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["pixels_written"] == 1
    assert result["pixels_skipped_by_selection"] == 1
    assert result["applied_runs"][0]["x"] == 1
    assert result["skipped_by_selection_runs"][0]["x"] == 0
    assert result["affected_cels"] == [
        {
            "layer_path": [1],
            "frame_number": 1,
            "position": {"x": 1, "y": 0},
            "bounds": {"x": 1, "y": 0, "width": 2, "height": 2},
            "linked_to_target": True,
        },
        {
            "layer_path": [1],
            "frame_number": 2,
            "position": {"x": 1, "y": 0},
            "bounds": {"x": 1, "y": 0, "width": 2, "height": 2},
            "linked_to_target": True,
        },
    ]
    assert result["linked_cels_preserved"] is True

    mask_target = tmp_path / "mask-selected.aseprite"
    mask = _apply(
        source,
        mask_target,
        _rgba_patch(x=0, y=0, length=2),
        selection={
            "kind": "mask",
            "bounds": {"x": 1, "y": 0, "width": 1, "height": 1},
            "rows": [{"y": 0, "runs": [{"x": 1, "length": 1}]}],
        },
    )
    assert mask.returncode == 0, mask.stdout
    mask_result = json.loads(mask.stdout)
    assert mask_result["applied_runs"][0]["x"] == 0
    assert mask_result["pixels_skipped_by_selection"] == 1


def test_empty_selection_is_a_reported_no_op(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "empty-selection.aseprite"
    _create(source)

    run = _apply(
        source,
        target,
        _rgba_patch(x=0, y=0, length=2),
        selection={"kind": "empty"},
    )

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["pixels_written"] == 0
    assert result["pixels_skipped_by_selection"] == 2
    assert result["before_content_digest"] == result["after_content_digest"]

    empty_patch_target = tmp_path / "empty-patch.aseprite"
    empty_patch = _apply(
        source,
        empty_patch_target,
        {
            "coordinate_space": "image-pixel",
            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
            "runs": [],
        },
    )
    assert empty_patch.returncode == 0, empty_patch.stdout
    empty_patch_result = json.loads(empty_patch.stdout)
    assert empty_patch_result["pixels_requested"] == 0
    assert empty_patch_result["before_content_digest"] == empty_patch_result[
        "after_content_digest"
    ]


def test_background_and_grayscale_writes_preserve_native_mode_and_opacity(
    tmp_path: Path,
) -> None:
    background = tmp_path / "background.aseprite"
    background_target = tmp_path / "background-target.aseprite"
    create = spa(
        "sprite",
        "create",
        "--input-json",
        json.dumps(
            {
                "target_sprite_file": str(background),
                "width": 2,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {
                    "kind": "background",
                    "background_color": {
                        "red": 0,
                        "green": 0,
                        "blue": 0,
                        "alpha": 255,
                    },
                },
                "overwrite": False,
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
            }
        ),
    )
    assert create.returncode == 0, create.stdout
    background_run = _apply(
        background, background_target, _rgba_patch(x=0, y=0, length=1)
    )
    assert background_run.returncode == 0, background_run.stdout
    background_result = json.loads(background_run.stdout)
    assert background_result["color_mode"] == "rgb"
    assert background_result["background_opaque"] is True

    translucent_target = tmp_path / "translucent-background.aseprite"
    translucent_patch = _rgba_patch(x=0, y=0, length=1)
    translucent_patch["runs"][0]["color"]["alpha"] = 1  # type: ignore[index]
    translucent = _apply(background, translucent_target, translucent_patch)
    assert translucent.returncode == 1, translucent.stdout
    assert not translucent_target.exists()

    grayscale = tmp_path / "grayscale.aseprite"
    grayscale_target = tmp_path / "grayscale-target.aseprite"
    _fixture(grayscale, "grayscale")
    gray_patch = {
        "coordinate_space": "image-pixel",
        "rectangle": {"x": 1, "y": 1, "width": 1, "height": 1},
        "runs": [
            {
                "x": 1,
                "y": 1,
                "length": 1,
                "color": {"kind": "grayscale", "gray": 123, "alpha": 231},
            }
        ],
    }
    gray_run = _apply(grayscale, grayscale_target, gray_patch)
    assert gray_run.returncode == 0, gray_run.stdout
    gray_result = json.loads(gray_run.stdout)
    assert gray_result["color_mode"] == "grayscale"
    assert gray_result["applied_runs"] == gray_patch["runs"]


def test_indexed_write_reports_effective_palette_and_rejects_missing_index_atomically(
    tmp_path: Path,
) -> None:
    source = tmp_path / "indexed.aseprite"
    target = tmp_path / "indexed-target.aseprite"
    _fixture(source, "indexed")
    source_bytes = source.read_bytes()
    valid_patch = {
        "coordinate_space": "image-pixel",
        "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
        "runs": [
            {
                "x": 0,
                "y": 0,
                "length": 1,
                "color": {"kind": "palette-index", "index": 1},
            }
        ],
    }

    valid = _apply(source, target, valid_patch)
    assert valid.returncode == 0, valid.stdout
    result = json.loads(valid.stdout)
    assert result["color_mode"] == "indexed"
    assert result["effective_palettes"] == [
        {
            "frame_number": 1,
            "palette_frame_number": 1,
            "palette_size": 2,
            "indexes": [
                {
                    "index": 1,
                    "color": {"red": 241, "green": 82, "blue": 65, "alpha": 255},
                }
            ],
        }
    ]

    invalid_target = tmp_path / "invalid-index.aseprite"
    invalid_patch = dict(valid_patch)
    invalid_patch["runs"] = [
        {
            "x": 0,
            "y": 0,
            "length": 1,
            "color": {"kind": "palette-index", "index": 2},
        }
    ]
    invalid = _apply(source, invalid_target, invalid_patch)
    assert invalid.returncode == 1, invalid.stdout
    assert not invalid_target.exists()
    assert source.read_bytes() == source_bytes


def test_apply_supports_explicit_in_place_target_commit(tmp_path: Path) -> None:
    source = tmp_path / "in-place.aseprite"
    _create(source)
    before = source.read_bytes()

    run = _apply(
        source,
        source,
        _rgba_patch(x=2, y=1, length=1),
        in_place=True,
        overwrite=True,
    )

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["target_commit"]["target_sprite_file"] == str(source)
    assert source.read_bytes() != before


def test_apply_resolves_the_complete_target_before_any_write(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "never-published.aseprite"
    _create(source)
    source_bytes = source.read_bytes()
    patch = _rgba_patch(x=0, y=0, length=1, width=4)
    patch["runs"] = [
        patch["runs"][0],  # type: ignore[index]
        {
            "x": 3,
            "y": 0,
            "length": 1,
            "color": {
                "kind": "rgba",
                "red": 68,
                "green": 85,
                "blue": 102,
                "alpha": 255,
            },
        },
    ]

    run = _apply(source, target, patch)

    assert run.returncode == 1, run.stdout
    assert not target.exists()
    assert source.read_bytes() == source_bytes


def test_apply_rejects_a_non_cel_target(tmp_path: Path) -> None:
    source = tmp_path / "group.aseprite"
    target = tmp_path / "group-target.aseprite"
    _fixture(source, "group")

    run = _apply(source, target, _rgba_patch(x=0, y=0, length=1))

    assert run.returncode == 1, run.stdout
    assert "not a regular Image Layer" in json.loads(run.stdout)["details"]["reason"]
    assert not target.exists()
