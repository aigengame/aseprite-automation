"""Installed Paint Operations against a real Aseprite executable."""

import hashlib
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.paint import PAINT_APPLY_HANDLER
from spa.ports import HandlerEvidence, RuntimeIssue
from spa.runtime.aseprite import invoke, probe
from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _fixture(target: Path, kind: str, *, palette_alpha: int | None = None) -> None:
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
        arguments = [
            str(prepared.executable),
            "--batch",
            "--script-param",
            f"kind={kind}",
            "--script-param",
            f"out={target}",
        ]
        if palette_alpha is not None:
            arguments.extend(["--script-param", f"palette_alpha={palette_alpha}"])
        arguments.extend(["--script", str(fixture)])
        run = subprocess.run(
            arguments,
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stdout + run.stderr
    assert target.is_file()
    if kind == "indexed-palette-change":
        _inject_palette_change(target)


def _inject_palette_change(target: Path) -> None:
    """Add a second-frame Palette Chunk unavailable through the public Lua API."""
    payload = bytearray(target.read_bytes())
    frame_offset = 128
    frame_offset += struct.unpack_from("<I", payload, frame_offset)[0]

    entries = struct.pack("<HBBBB", 0, 0, 0, 0, 0) + struct.pack(
        "<HBBBB", 0, 65, 105, 225, 255
    )
    chunk_data = struct.pack("<III8x", 2, 0, 1) + entries
    chunk = struct.pack("<IH", len(chunk_data) + 6, 0x2019) + chunk_data
    frame_size = struct.unpack_from("<I", payload, frame_offset)[0]
    insert_at = frame_offset + 16
    old_chunk_count = struct.unpack_from("<H", payload, frame_offset + 6)[0]
    new_chunk_count = struct.unpack_from("<I", payload, frame_offset + 12)[0]
    struct.pack_into("<I", payload, frame_offset, frame_size + len(chunk))
    if new_chunk_count:
        struct.pack_into("<I", payload, frame_offset + 12, new_chunk_count + 1)
    else:
        struct.pack_into("<H", payload, frame_offset + 6, old_chunk_count + 1)
    payload[insert_at:insert_at] = chunk
    struct.pack_into("<I", payload, 0, len(payload))
    target.write_bytes(payload)


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


@pytest.mark.parametrize("runs", [[], None])
def test_reject_clipping_validates_the_declared_rectangle_before_writes(
    tmp_path: Path, runs: list[object] | None
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "outside-rectangle.aseprite"
    _create(source)
    source_bytes = source.read_bytes()
    patch = _rgba_patch(x=0, y=0, length=1, width=4)
    if runs == []:
        patch["runs"] = []

    run = _apply(source, target, patch)

    assert run.returncode == 1, run.stdout
    assert (
        "Rectangle is outside Image bounds"
        in json.loads(run.stdout)["details"]["reason"]
    )
    assert not target.exists()
    assert source.read_bytes() == source_bytes


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
    assert (
        empty_patch_result["before_content_digest"]
        == empty_patch_result["after_content_digest"]
    )


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


@pytest.mark.parametrize("palette_alpha", [0, 128])
def test_indexed_background_rejects_translucent_palette_write_atomically(
    tmp_path: Path, palette_alpha: int
) -> None:
    source = tmp_path / "indexed-background.aseprite"
    target = tmp_path / "indexed-background-target.aseprite"
    _fixture(source, "indexed-background", palette_alpha=palette_alpha)
    source_bytes = source.read_bytes()
    patch = {
        "coordinate_space": "image-pixel",
        "rectangle": {"x": 1, "y": 0, "width": 1, "height": 1},
        "runs": [
            {
                "x": 1,
                "y": 0,
                "length": 1,
                "color": {"kind": "palette-index", "index": 0},
            }
        ],
    }

    run = _apply(source, target, patch)

    assert run.returncode == 1, run.stdout
    assert (
        "persisted Background Image is not opaque"
        in json.loads(run.stdout)["details"]["reason"]
    )
    assert not target.exists()
    assert source.read_bytes() == source_bytes


def test_indexed_background_accepts_opaque_transparent_index(
    tmp_path: Path,
) -> None:
    source = tmp_path / "indexed-background.aseprite"
    target = tmp_path / "indexed-background-target.aseprite"
    _fixture(source, "indexed-background", palette_alpha=255)
    patch = {
        "coordinate_space": "image-pixel",
        "rectangle": {"x": 1, "y": 0, "width": 1, "height": 1},
        "runs": [
            {
                "x": 1,
                "y": 0,
                "length": 1,
                "color": {"kind": "palette-index", "index": 0},
            }
        ],
    }

    run = _apply(source, target, patch)

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert result["pixels_changed"] == 1
    assert result["background_opaque"] is True
    assert target.is_file()


def test_indexed_linked_cels_report_each_frames_effective_palette(
    tmp_path: Path,
) -> None:
    source = tmp_path / "palette-change.aseprite"
    target = tmp_path / "palette-change-target.aseprite"
    _fixture(source, "indexed-palette-change")
    patch = {
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

    run = _apply(
        source,
        target,
        patch,
        address={"layer_path": [1], "frame_number": 3},
    )

    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1, 3]
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
        },
        {
            "frame_number": 3,
            "palette_frame_number": 2,
            "palette_size": 2,
            "indexes": [
                {
                    "index": 1,
                    "color": {"red": 65, "green": 105, "blue": 225, "alpha": 255},
                }
            ],
        },
    ]


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


def test_apply_accepts_in_place_paths_to_the_same_publication_entry(
    tmp_path: Path,
) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    alias_dir = tmp_path / "alias"
    alias_dir.symlink_to(real_dir, target_is_directory=True)
    target = real_dir / "sprite.aseprite"
    source = alias_dir / "sprite.aseprite"
    _create(target)
    before = source.read_bytes()

    run = _apply(
        source,
        target,
        _rgba_patch(x=2, y=1, length=1),
        in_place=True,
        overwrite=True,
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["target_commit"]["target_sprite_file"] == str(target)
    assert alias_dir.is_symlink()
    assert source.read_bytes() == target.read_bytes() != before


@pytest.mark.parametrize("in_place", [False, True])
def test_apply_case_variant_publication_entry_requires_in_place_intent(
    tmp_path: Path, in_place: bool
) -> None:
    marker = tmp_path / "CaseProbe"
    marker.touch()
    if not (tmp_path / "caseprobe").exists():
        pytest.skip("requires a case-insensitive filesystem")
    source = tmp_path / "Sprite.aseprite"
    _create(source)
    target = tmp_path / "sprite.aseprite"
    before = source.read_bytes()

    run = _apply(
        source,
        target,
        _rgba_patch(x=2, y=1, length=1),
        in_place=in_place,
        overwrite=True,
    )

    if in_place:
        assert run.returncode == 0, run.stdout + run.stderr
        assert source.read_bytes() != before
    else:
        assert run.returncode == 2, run.stdout + run.stderr
        assert json.loads(run.stdout)["code"] == "invalid_request"
        assert source.read_bytes() == before


@pytest.mark.parametrize("through_target_symlink", [False, True])
def test_apply_rejects_source_alias_to_target_without_commit(
    tmp_path: Path, through_target_symlink: bool
) -> None:
    real = tmp_path / "real.aseprite"
    _create(real)
    target = real
    if through_target_symlink:
        target = tmp_path / "target.aseprite"
        target.symlink_to(real)
    source = tmp_path / "source.aseprite"
    source.symlink_to(target)
    before = source.read_bytes()

    for in_place in (False, True):
        run = _apply(
            source,
            target,
            _rgba_patch(x=0, y=0, length=1),
            in_place=in_place,
            overwrite=True,
        )

        assert run.returncode == 2, run.stdout + run.stderr
        assert json.loads(run.stdout)["code"] == "invalid_request"
        assert source.is_symlink()
        assert target.is_symlink() is through_target_symlink
        assert source.read_bytes() == before
        assert real.read_bytes() == before


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


@pytest.mark.parametrize(
    ("kind", "address", "reason"),
    [
        ("group", {"layer_path": [1], "frame_number": 1}, "not a regular"),
        ("reference", {"layer_path": [1], "frame_number": 1}, "not a regular"),
        ("tilemap", {"layer_path": [1], "frame_number": 1}, "not a regular"),
        ("absent", {"layer_path": [1], "frame_number": 2}, "does not exist"),
    ],
)
def test_apply_rejects_unsupported_or_absent_cel_targets(
    tmp_path: Path, kind: str, address: dict[str, object], reason: str
) -> None:
    source = tmp_path / f"{kind}.aseprite"
    target = tmp_path / f"{kind}-target.aseprite"
    _fixture(source, kind)

    run = _apply(source, target, _rgba_patch(x=0, y=0, length=1), address=address)

    assert run.returncode == 1, run.stdout
    assert reason in json.loads(run.stdout)["details"]["reason"]
    assert not target.exists()


def test_apply_ignores_ambient_editor_selection(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "ambient-selection-target.aseprite"
    _create(source)
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    fixture = Path(__file__).parent / "fixtures" / "ambient_selection.lua"
    support = Path(__file__).parents[2] / "src" / "spa" / "kernel"
    with tempfile.TemporaryDirectory(prefix="spa-paint-selection-") as work:
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
                f"source={source}",
                "--script-param",
                f"target={target}",
                "--script-param",
                f"paint={support / 'paint_apply_support.lua'}",
                "--script-param",
                f"digest={support / 'digest.lua'}",
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


def test_single_pixel_patch_on_2k_sprite_completes_with_default_timeout(
    tmp_path: Path,
) -> None:
    source = tmp_path / "large.aseprite"
    target = tmp_path / "large-target.aseprite"
    _fixture(source, "large-rgb")

    run = _apply(source, target, _rgba_patch(x=0, y=0, length=1))

    assert run.returncode == 0, run.stdout
    assert json.loads(run.stdout)["pixels_written"] == 1
    assert target.is_file()


def test_kernel_accepts_256_addressed_pixels_and_rejects_257(tmp_path: Path) -> None:
    source = tmp_path / "limit.aseprite"
    _fixture(source, "limit-rgb")
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )

    def payload(length: int) -> dict[str, object]:
        return {
            "source_sprite_file": str(source),
            "staged_sprite_file": str(tmp_path / f"limit-{length}-staged.aseprite"),
            "target": {"layer_path": [1], "frame_number": 1},
            "patch": {
                "coordinate_space": "image-pixel",
                "rectangle": {"x": 0, "y": 0, "width": length, "height": 1},
                "runs": [
                    {
                        "x": 0,
                        "y": 0,
                        "length": length,
                        "color": {
                            "kind": "rgba",
                            "red": 1,
                            "green": 2,
                            "blue": 3,
                            "alpha": 255,
                        },
                    }
                ],
            },
            "clipping": "reject",
            "selection": None,
        }

    accepted = invoke(observation, PAINT_APPLY_HANDLER, payload(256), 15.0)
    assert accepted.payload["pixels_requested"] == 256
    assert (tmp_path / "limit-256-staged.aseprite").is_file()

    with pytest.raises(RuntimeIssue) as rejected:
        invoke(observation, PAINT_APPLY_HANDLER, payload(257), 15.0)
    assert rejected.value.kind == "handler_rejected"
    assert isinstance(rejected.value.evidence, HandlerEvidence)
    assert "Operation Limit" in rejected.value.evidence.reason
    assert not (tmp_path / "limit-257-staged.aseprite").exists()
