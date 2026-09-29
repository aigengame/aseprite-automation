"""Native Indexed Paint Composite coverage at the public CLI boundary."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.contracts import RuntimeRequest
from spa.descriptors import PROBE_RESOURCES
from spa.runtime.aseprite import probe
from spa.runtime.invocation import prepare_invocation
from tests.support import inject_palette_change, spa

pytestmark = pytest.mark.e2e

FRAME_2_PALETTE = [
    (0, 0, 0, 255),
    (0, 0, 255, 255),
    (0, 200, 0, 255),
    (255, 255, 0, 255),
    (0, 255, 255, 255),
    (255, 0, 255, 255),
    (128, 128, 128, 255),
    (0, 0, 0, 0),
    (255, 0, 0, 255),
]


def _call(*command: str, **request: object) -> tuple[int, dict]:
    run = spa(
        *command,
        "--input-json",
        "-",
        stdin=json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"], **request}),
    )
    assert run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)


def _fixture(path: Path, *, kind: str = "independent") -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    with tempfile.TemporaryDirectory(prefix="spa-composite-indexed-") as work:
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
                f"out={path}",
                "--script",
                str(Path(__file__).parent / "fixtures" / "composite_indexed.lua"),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stdout + run.stderr
    assert path.is_file()


def _snapshot(*indexes: int) -> dict:
    runs: list[dict] = []
    for index in indexes:
        if runs and runs[-1]["color"]["index"] == index:
            runs[-1]["length"] += 1
        else:
            runs.append(
                {"length": 1, "color": {"kind": "palette-index", "index": index}}
            )
    return {
        "coordinate_space": "image-pixel",
        "color_mode": "indexed",
        "rectangle": {"x": 0, "y": 0, "width": len(indexes), "height": 1},
        "rows": [runs],
    }


def _compose(
    source: Path, output: Path, *indexes: int, **options: object
) -> tuple[int, dict]:
    request: dict[str, object] = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(output),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
        "input": {"kind": "inline", "snapshot": _snapshot(*indexes)},
        "position": {"x": 0, "y": 0},
        "opacity": 255,
        "blend_mode": "normal",
        "palette_frame_number": 2,
    }
    request.update(options)
    return _call(
        "paint",
        "composite",
        **request,
    )


def _image(path: Path, frame: int) -> dict:
    code, result = _call(
        "image",
        "get",
        sprite_file=str(path),
        source={
            "kind": "individual",
            "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
            "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
        },
    )
    assert code == 0, result
    return result


def _indexes(path: Path, frame: int) -> list[int]:
    result = _image(path, frame)
    return [
        run["color"]["index"]
        for run in result["snapshot"]["rows"][0]
        for _ in range(run["length"])
    ]


def test_frame_two_effective_palette_composes_mask_and_new_index(
    tmp_path: Path,
) -> None:
    source = tmp_path / "palette-change.aseprite"
    target = tmp_path / "composited.aseprite"
    _fixture(source)
    inject_palette_change(source, FRAME_2_PALETTE, frame_number=2)
    original = source.read_bytes()

    code, result = _compose(source, target, 7, 8)

    assert code == 0, result
    first, second = _image(target, 1), _image(target, 2)
    assert _indexes(target, 2) == [1, 8]
    assert _indexes(target, 1) == [1, 1]
    assert result["composite_palette_basis"]["frame_number"] == 2
    assert result["composite_palette_basis"]["palette_frame_number"] == 2
    assert [
        entry["index"] for entry in result["composite_palette_basis"]["indexes"]
    ] == [1, 7, 8]
    assert first["effective_palettes"] == [
        {
            "frame_number": 1,
            "palette_frame_number": 1,
            "palette_size": 8,
            "indexes": [
                {
                    "index": 1,
                    "color": {"red": 20, "green": 0, "blue": 0, "alpha": 255},
                }
            ],
        }
    ]
    assert second["effective_palettes"][0]["palette_size"] == 9
    assert second["effective_palettes"][0]["indexes"][-1] == {
        "index": 8,
        "color": {"red": 255, "green": 0, "blue": 0, "alpha": 255},
    }
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() == original


def _atomic_refusal(
    source: Path,
    output: Path,
    indexes: tuple[int, ...],
    expected_code: str,
    **options: object,
) -> dict:
    original = source.read_bytes()
    sentinel = b"existing target must remain intact"
    output.write_bytes(sentinel)
    code, result = _compose(source, output, *indexes, overwrite=True, **options)
    assert code == 2, result
    assert result["code"] == expected_code, result
    assert source.read_bytes() == original
    assert output.read_bytes() == sentinel
    return result


def test_linked_cels_share_indexed_image_and_report_each_palette(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "linked.aseprite", tmp_path / "linked-out.aseprite"
    _fixture(source, kind="linked")
    inject_palette_change(source, FRAME_2_PALETTE, frame_number=2)
    original = source.read_bytes()

    code, result = _compose(source, target, 7, 2)

    assert code == 0, result
    assert result["native_sharing_preserved"] is True
    assert [cel["frame_number"] for cel in result["affected_cels"]] == [1, 2]
    assert [
        (palette["frame_number"], palette["palette_frame_number"])
        for palette in result["effective_palettes"]
    ] == [(1, 1), (2, 2)]
    assert _indexes(target, 1) == _indexes(target, 2) == [1, 2]
    assert source.read_bytes() == original


def test_linked_other_frame_missing_source_index_rejects_atomically(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "linked.aseprite", tmp_path / "unchanged.aseprite"
    _fixture(source, kind="linked")
    inject_palette_change(source, FRAME_2_PALETTE, frame_number=2)

    _atomic_refusal(source, target, (7, 8), "paint_composite_invalid")


def test_indexed_background_accepts_opaque_result(tmp_path: Path) -> None:
    source, target = tmp_path / "background.aseprite", tmp_path / "result.aseprite"
    _fixture(source, kind="background")
    original = source.read_bytes()

    code, result = _compose(
        source,
        target,
        7,
        8,
        target={"layer": {"layer_path": [1]}, "frame_number": 1},
        palette_frame_number=1,
    )

    assert code == 0, result
    assert result["background_opaque"] is True
    assert _indexes(target, 1) == [1, 8]
    assert source.read_bytes() == original


def test_indexed_background_rejects_translucent_palette_output(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "background.aseprite", tmp_path / "unchanged.aseprite"
    _fixture(source, kind="background-alpha")

    _atomic_refusal(
        source,
        target,
        (7, 8),
        "paint_composite_invalid",
        target={"layer": {"layer_path": [1]}, "frame_number": 1},
        palette_frame_number=1,
    )


@pytest.mark.parametrize("palette_number", [None, 1])
def test_missing_or_wrong_palette_frame_number_rejects_atomically(
    tmp_path: Path, palette_number: int | None
) -> None:
    source, target = tmp_path / "changed.aseprite", tmp_path / "unchanged.aseprite"
    _fixture(source)
    inject_palette_change(source, FRAME_2_PALETTE, frame_number=2)

    _atomic_refusal(
        source,
        target,
        (7, 8),
        "paint_composite_invalid",
        palette_frame_number=palette_number,
    )


def test_source_index_outside_target_palette_rejects_atomically(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "changed.aseprite", tmp_path / "unchanged.aseprite"
    _fixture(source)
    inject_palette_change(source, FRAME_2_PALETTE, frame_number=2)

    _atomic_refusal(source, target, (7, 9), "paint_composite_invalid")


def test_missing_transparent_index_in_palette_rejects_atomically(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "missing-mask.aseprite", tmp_path / "unchanged.aseprite"
    _fixture(source, kind="missing-mask")

    _atomic_refusal(
        source,
        target,
        (7, 1),
        "paint_composite_invalid",
        target={"layer": {"layer_path": [1]}, "frame_number": 1},
        palette_frame_number=1,
    )


@pytest.mark.parametrize(
    "blend,opacity", [("normal", 0), ("normal", 127), ("multiply", 255)]
)
def test_unsupported_indexed_blend_or_opacity_is_typed_gap(
    tmp_path: Path, blend: str, opacity: int
) -> None:
    source, target = tmp_path / "changed.aseprite", tmp_path / "unchanged.aseprite"
    _fixture(source)
    inject_palette_change(source, FRAME_2_PALETTE, frame_number=2)

    _atomic_refusal(
        source,
        target,
        (7, 8),
        "paint_composite_unsupported",
        blend_mode=blend,
        opacity=opacity,
    )


def test_selection_uses_canvas_position_and_preserves_nonzero_mask(
    tmp_path: Path,
) -> None:
    source = tmp_path / "offset.aseprite"
    _fixture(source, kind="offset")
    inject_palette_change(source, FRAME_2_PALETTE, frame_number=2)
    original = source.read_bytes()
    selection = {"kind": "all", "rectangle": {"x": 2, "y": 0, "width": 1, "height": 1}}

    target = tmp_path / "selected.aseprite"
    code, result = _compose(source, target, 2, 8, selection=selection)

    assert code == 0, result
    assert result["applied_runs"] == [{"x": 1, "y": 0, "length": 1}]
    assert result["skipped_by_selection_runs"] == [{"x": 0, "y": 0, "length": 1}]
    assert _indexes(target, 2) == [1, 8]

    mask_target = tmp_path / "mask.aseprite"
    mask_selection = {
        "kind": "all",
        "rectangle": {"x": 1, "y": 0, "width": 2, "height": 1},
    }
    code, mask_result = _compose(source, mask_target, 7, 8, selection=mask_selection)
    assert code == 0, mask_result
    assert _indexes(mask_target, 2) == [1, 8]
    assert source.read_bytes() == original


def test_indexed_helper_closes_scratch_and_restores_context_after_error(
    tmp_path: Path,
) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    support = Path(__file__).parents[2] / "src" / "spa" / "kernel"
    output = tmp_path / "helper.json"
    with tempfile.TemporaryDirectory(prefix="spa-composite-helper-") as work:
        prepared = prepare_invocation(
            Path(observation.canonical_path),
            Path(observation.resource_path),
            Path(work),
        )
        args = [str(prepared.executable), "--batch"]
        for key, value in {
            "kind": "helper",
            "out": str(output),
            "paint_composite": str(support / "paint_composite_support.lua"),
            "image_snapshot": str(support / "image_snapshot.lua"),
            "raster_color": str(support / "raster_color.lua"),
            "effective_palette": str(support / "effective_palette.lua"),
            "selection_mask": str(support / "selection_mask.lua"),
        }.items():
            args.extend(("--script-param", f"{key}={value}"))
        args.extend(
            (
                "--script",
                str(Path(__file__).parent / "fixtures" / "composite_indexed.lua"),
            )
        )
        run = subprocess.run(
            args, text=True, capture_output=True, check=False, env=prepared.environment
        )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(output.read_text())
    assert result["successful"] is True
    assert result["restored_after_error"] is True, result
