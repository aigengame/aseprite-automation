"""Image Resize through the installed CLI and a real Aseprite runtime."""

import json
import os
import subprocess
import tempfile
from importlib.resources import files
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.image.support import export_image as _export
from tests.image.support import image_fixture as _fixture
from tests.image.support import inspect_native as _inspect_native
from tests.support import inject_palette_change, process_diagnostics, spa

pytestmark = pytest.mark.e2e


def _resize(source: Path, output: Path, **options: object) -> tuple[int, dict]:
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(output),
        "in_place": False,
        "overwrite": False,
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "width": 4,
        "height": 4,
        "method": "nearest-neighbor",
        "position_policy": {"kind": "keep"},
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        **options,
    }
    run = spa("image", "resize", "--input-json", json.dumps(request))
    return run.returncode, json.loads(run.stdout)


def test_resize_keeps_cel_position_and_persists_native_pixels(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    target = tmp_path / "resized.aseprite"

    code, result = _resize(source, target)

    assert code == 0, result
    assert result["requested_size"] == {"width": 4, "height": 4}
    assert result["effective_size"] == {"width": 4, "height": 4}
    assert result["old_size"] == {"width": 2, "height": 2}
    assert result["method"] == "nearest-neighbor"
    assert result["affected_cels"][0]["before_position"] == {"x": 1, "y": 2}
    assert result["affected_cels"][0]["after_position"] == {"x": 1, "y": 2}
    assert result["persisted_reopen_verified"] is True
    assert target.is_file()
    assert source.read_bytes() != target.read_bytes()

    pixels = _export(target, tmp_path / "resized.png")
    assert pixels.getpixel((1, 2)) == (255, 0, 0, 255)
    assert pixels.getpixel((4, 2)) == (0, 0, 255, 255)


@pytest.mark.parametrize(
    ("rounding", "applied_x", "applied_y"),
    [
        ("toward-zero", 0, 0),
        ("floor", -1, 0),
        ("ceil", 0, 1),
        ("nearest-away-from-zero", -1, 1),
    ],
)
def test_linked_image_pivot_uses_one_exact_offset_for_every_cel(
    tmp_path: Path, rounding: str, applied_x: int, applied_y: int
) -> None:
    source = _fixture(tmp_path, "linked")
    target = tmp_path / "resized.aseprite"
    code, result = _resize(
        source,
        target,
        target={"layer": {"layer_path": [1]}, "frame_number": 2},
        width=3,
        height=3,
        position_policy={
            "kind": "pivot",
            "pivot_x": 1,
            "pivot_y": -1,
            "rounding": rounding,
        },
    )

    assert code == 0, result
    assert result["offset_x"] == {
        "numerator": -1,
        "denominator": 2,
        "applied": applied_x,
    }
    assert result["offset_y"] == {
        "numerator": 1,
        "denominator": 2,
        "applied": applied_y,
    }
    affected = result["affected_cels"]
    assert [cel["frame_number"] for cel in affected] == [1, 2]
    assert [cel["before_position"] for cel in affected] == [
        {"x": 1, "y": 2},
        {"x": 1, "y": 2},
    ]
    assert [cel["after_position"] for cel in affected] == [
        {"x": 1 + applied_x, "y": 2 + applied_y},
        {"x": 1 + applied_x, "y": 2 + applied_y},
    ]
    assert result["native_sharing_preserved"] is True
    assert result["before_content_digest"] != result["after_content_digest"]
    assert result["persisted_reopen_verified"] is True

    for frame_number, expected_partner in ((1, 2), (2, 1)):
        run = spa(
            "cel",
            "get",
            "--input-json",
            json.dumps(
                {
                    "sprite_file": str(target),
                    "target": {
                        "layer": {"layer_path": [1]},
                        "frame_number": frame_number,
                    },
                    "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                }
            ),
        )
        assert run.returncode == 0, run.stdout
        persisted = json.loads(run.stdout)["cel"]
        assert persisted["position"] == affected[frame_number - 1]["after_position"]
        assert persisted["image_bounds"]["width"] == 3
        assert persisted["image_bounds"]["height"] == 3
        assert persisted["linked_cels"] == [
            {"layer_path": [1], "frame_number": expected_partner}
        ]


def test_indexed_bilinear_uses_declared_effective_palette(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "indexed")
    original = source.read_bytes()
    target = tmp_path / "indexed-resized.aseprite"

    code, result = _resize(source, target, method="bilinear", palette_frame_number=1)

    assert code == 0, result
    assert result["color_mode"] == "indexed"
    assert result["effective_palette"] == {
        "requested_frame_number": 1,
        "palette_frame_number": 1,
        "palette_size": 4,
        "transparent_color_index": 0,
    }
    assert result["native_sharing_preserved"] is True
    assert source.read_bytes() == original
    center = _inspect_native(target, tmp_path, 1, 1)
    assert center == {
        "pixel": 3,
        "transparent_index": 0,
        "width": 4,
        "height": 4,
        "palette_color": {"red": 127, "green": 0, "blue": 127, "alpha": 255},
    }


def test_indexed_bilinear_resolves_palette_before_requested_frame(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "indexed-two-frame")
    code, result = _resize(
        source,
        tmp_path / "indexed-later.aseprite",
        method="bilinear",
        palette_frame_number=2,
    )
    assert code == 0, result
    assert result["effective_palette"]["requested_frame_number"] == 2
    assert result["effective_palette"]["palette_frame_number"] == 1


def test_indexed_bilinear_preserves_transparent_index_edge(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "indexed-edge")
    original = source.read_bytes()
    target = tmp_path / "indexed-edge-resized.aseprite"

    code, result = _resize(source, target, method="bilinear", palette_frame_number=1)

    assert code == 0, result
    assert result["effective_palette"]["transparent_color_index"] == 0
    assert source.read_bytes() == original
    assert _inspect_native(target, tmp_path, 0, 0)["pixel"] == 1
    assert _inspect_native(target, tmp_path, 3, 3)["pixel"] == 0


@pytest.mark.parametrize(
    ("mode", "expected_row"),
    [
        ("indexed-offset-mask", [1, 3, 3, 2]),
        ("indexed-offset-mask-zero-before", [1, 3, 3, 2]),
        ("indexed-offset-mask-zero-after", [1, 4, 4, 2]),
        ("indexed-offset-mask-black", [0, 0, 0, 2]),
        ("indexed-offset-mask-duplicate", [1, 1, 0, 2]),
        ("indexed-offset-mask-large-palette", [1, 3, 3, 2]),
    ],
)
def test_indexed_bilinear_honors_nonzero_transparent_index(
    tmp_path: Path, mode: str, expected_row: list[int]
) -> None:
    source = _fixture(tmp_path, mode)
    original = source.read_bytes()
    target = tmp_path / "offset-mask-resized.aseprite"

    code, result = _resize(source, target, method="bilinear", palette_frame_number=1)

    assert code == 0, result
    assert result["effective_palette"]["transparent_color_index"] == 2
    assert result["effective_palette"]["palette_size"] == (
        257 if mode.endswith("large-palette") else 5
    )
    assert source.read_bytes() == original
    persisted = _inspect_native(target, tmp_path, 0, 0, row=True)
    assert persisted["row"] == expected_row
    assert persisted["pixel"] == expected_row[0]
    assert persisted["transparent_index"] == 2
    assert persisted["transparent_entry"] == {
        "red": 0,
        "green": 0,
        "blue": 255,
        "alpha": 255,
    }


def test_shared_resize_restores_active_context_on_success_and_failure(
    tmp_path: Path,
) -> None:
    observation = probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
    output = tmp_path / "context.json"
    with tempfile.TemporaryDirectory(prefix="spa-image-context-") as work:
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
                f"image_resize_transform={files('spa.kernel').joinpath('raster/image/image_resize_transform.lua')}",
                "--script-param",
                f"effective_palette={files('spa.kernel').joinpath('color/effective_palette.lua')}",
                "--script-param",
                f"out={output}",
                "--script",
                str(
                    Path(__file__).parent / "fixtures" / "resize_transform_context.lua"
                ),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, process_diagnostics(run)
    result = json.loads(output.read_text())
    assert result["before"] == {"sprite": True, "layer": True, "frame": True}
    assert result["success"] is True
    assert result["resized_width"] == 3
    assert result["after_success"] == result["before"]
    assert result["failure"] is False
    assert result["after_failure"] == result["before"]
    assert result["no_sprite_success"] is True
    assert result["after_no_sprite"] is True


def test_indexed_bilinear_uses_declared_palette_change_in_pixel_result(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "indexed-two-frame")
    inject_palette_change(
        source,
        [
            (0, 0, 0, 0),
            (0, 255, 0, 255),
            (255, 255, 0, 255),
            (0, 0, 0, 255),
        ],
    )
    first_code, first = _resize(
        source,
        tmp_path / "first-palette.aseprite",
        method="bilinear",
        palette_frame_number=1,
    )
    second_code, second = _resize(
        source,
        tmp_path / "second-palette.aseprite",
        method="bilinear",
        palette_frame_number=2,
    )
    assert first_code == second_code == 0, (first, second)
    assert first["effective_palette"]["palette_frame_number"] == 1
    assert second["effective_palette"]["palette_frame_number"] == 2
    assert first["after_content_digest"] != second["after_content_digest"]


def test_indexed_bilinear_requires_a_valid_palette_frame_atomically(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "indexed")
    original = source.read_bytes()
    for palette_frame_number in (None, 99):
        target = tmp_path / f"rejected-{palette_frame_number}.aseprite"
        code, failure = _resize(
            source, target, method="bilinear", palette_frame_number=palette_frame_number
        )
        assert code == 2, failure
        assert failure["code"] == "image_resize_palette_basis_invalid"
        assert not target.exists()
        assert source.read_bytes() == original


def test_grayscale_bilinear_preserves_transparent_edge_color_without_mutating_source(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path, "grayscale")
    original = source.read_bytes()
    target = tmp_path / "grayscale-resized.aseprite"

    code, result = _resize(source, target, method="bilinear")

    assert code == 0, result
    assert result["color_mode"] == "grayscale"
    assert result["effective_palette"] is None
    assert source.read_bytes() == original
    center = _inspect_native(target, tmp_path, 1, 1)
    assert center["width"] == center["height"] == 4
    assert center["gray"] == 200
    assert center["alpha"] == 113


def test_rgb_bilinear_repairs_transparent_edge_on_a_source_copy(tmp_path: Path) -> None:
    source = _fixture(tmp_path, "rgb-edge")
    original = source.read_bytes()
    target = tmp_path / "rgb-edge-resized.aseprite"
    code, result = _resize(source, target, method="bilinear")
    assert code == 0, result
    assert source.read_bytes() == original
    center = _inspect_native(target, tmp_path, 1, 1)
    assert center["red"] == 255
    assert center["green"] == center["blue"] == 0
    assert center["alpha"] == 113


def test_rotsprite_resize_persists_requested_size_and_method(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    target = tmp_path / "rotsprite.aseprite"
    code, result = _resize(source, target, method="rotsprite", width=3, height=3)
    assert code == 0, result
    assert result["method"] == "rotsprite"
    assert result["effective_size"] == {"width": 3, "height": 3}
    assert result["affected_cels"][0]["after_position"] == {"x": 1, "y": 2}
    assert result["persisted_reopen_verified"] is True
    assert _inspect_native(target, tmp_path, 0, 0)["red"] == 255


@pytest.mark.parametrize(
    ("mode", "address", "code"),
    [
        ("absent", {"layer_path": [1], "frame_number": 2}, "cel_not_found"),
        (
            "background",
            {"layer_path": [1], "frame_number": 1},
            "cel_unsupported_target",
        ),
        ("reference", {"layer_path": [1], "frame_number": 1}, "cel_unsupported_target"),
        ("tilemap", {"layer_path": [2], "frame_number": 1}, "cel_unsupported_target"),
    ],
)
def test_unsupported_or_absent_cel_is_rejected_without_publication(
    tmp_path: Path, mode: str, address: dict, code: str
) -> None:
    source = _fixture(tmp_path, mode)
    original = source.read_bytes()
    target = tmp_path / "rejected.aseprite"

    status, failure = _resize(
        source,
        target,
        target={
            "layer": {"layer_path": address["layer_path"]},
            "frame_number": address["frame_number"],
        },
    )

    assert status == 2, failure
    assert failure["code"] == code
    assert not target.exists()
    assert source.read_bytes() == original


def test_out_of_range_pivot_refuses_in_place_change_atomically(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    original = source.read_bytes()

    status, failure = _resize(
        source,
        source,
        in_place=True,
        overwrite=True,
        position_policy={
            "kind": "pivot",
            "pivot_x": 2**31 - 1,
            "pivot_y": 0,
            "rounding": "floor",
        },
    )

    assert status == 2, failure
    assert failure["code"] == "image_resize_position_out_of_bounds"
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("options", "failure_code"),
    [
        ({"width": 0}, "invalid_request"),
        ({"method": "bicubic"}, "invalid_request"),
        ({"method": "nearest-neighbor", "palette_frame_number": 1}, "invalid_request"),
        ({"position_policy": {"kind": "pivot", "pivot_x": 1}}, "invalid_request"),
        (
            {
                "width": 2,
                "height": 2,
                "position_policy": {
                    "kind": "pivot",
                    "pivot_x": 2**31,
                    "pivot_y": 0,
                    "rounding": "floor",
                },
            },
            "invalid_request",
        ),
        (
            {"method": "bilinear", "palette_frame_number": 1},
            "image_resize_palette_basis_invalid",
        ),
    ],
)
def test_invalid_resize_intent_has_no_target_file(
    tmp_path: Path, options: dict, failure_code: str
) -> None:
    source = _fixture(tmp_path)
    target = tmp_path / "rejected.aseprite"
    status, failure = _resize(source, target, **options)
    assert status == 2, failure
    assert failure["code"] == failure_code
    assert not target.exists()
