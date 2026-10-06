"""Static PNG Color Mode choices, bounded Palette preparation, and opacity."""

import json
from pathlib import Path

import pytest
from PIL import Image

from spa.contracts.digest import fnv1a64
from tests.color_mode.test_e2e_color_mode import conversion_for, convert
from tests.export.support import source_sprite
from tests.export.test_e2e_static_geometry import _export, _request
from tests.support import inject_palette_change, spa

pytestmark = pytest.mark.e2e
MODES = ("rgb", "grayscale", "indexed")


def _source(tmp_path: Path, mode: str = "rgb", scenario: str = "basic") -> Path:
    return source_sprite(
        tmp_path, "static_color_modes.lua", mode=mode, scenario=scenario
    )


def _pixels(destination: Path) -> list[tuple[int, int, int, int]]:
    with Image.open(destination) as image:
        return list(image.convert("RGBA").get_flattened_data())


@pytest.mark.parametrize(
    ("source_mode", "target_mode"),
    [(source, target) for source in MODES for target in MODES],
)
def test_explicit_conversion_and_same_mode_preserve_neutral_samples_and_alpha(
    tmp_path: Path, source_mode: str, target_mode: str
) -> None:
    source = _source(tmp_path, source_mode)
    before = source.read_bytes()
    destination = tmp_path / "converted.png"
    choices = {"color_mode": conversion_for(source_mode, target_mode)}
    if source_mode != "indexed" and target_mode == "indexed":
        choices["palette_preparation"] = {"kind": "current"}
    result = _export(_request(source, destination, **choices))

    assert result["source_color_mode"] == source_mode
    assert result["color_mode"] == target_mode
    assert result["requested_parameters"]["color_mode"] == choices["color_mode"]
    assert _pixels(destination)[0] == (90, 90, 90, 255)
    assert _pixels(destination)[1][3] == 0
    with Image.open(destination) as image:
        assert (
            image.mode
            == {"rgb": "RGBA", "grayscale": "LA", "indexed": "P"}[target_mode]
        )
    assert source.read_bytes() == before
    assert not list(tmp_path.glob("*.staged.*"))


@pytest.mark.parametrize("algorithm", ("none", "ordered", "old", "error-diffusion"))
def test_dithering_matches_existing_native_conversion_and_one_file_matrix(
    tmp_path: Path, algorithm: str
) -> None:
    source = _source(tmp_path, scenario="dither")
    before = source.read_bytes()
    dithering: dict = {"algorithm": algorithm}
    if algorithm == "ordered":
        dithering["matrix"] = {"kind": "installed", "id": "bayer4x4"}
    elif algorithm == "error-diffusion":
        dithering["dithering_factor"] = 0.5
    conversion = conversion_for("rgb", "indexed")
    conversion["target"]["dithering"] = dithering
    code, native = convert(source, tmp_path / "native.aseprite", conversion)
    assert code == 0, native
    destination = tmp_path / "dithered.png"
    result = _export(
        _request(
            source,
            destination,
            color_mode=conversion,
            palette_preparation={"kind": "current"},
        )
    )

    assert result["requested_parameters"]["color_mode"] == conversion
    assert result["alpha_channel"]["minimum"] == 255
    with Image.open(destination) as image:
        assert image.mode == "P" and image.size == (8, 4)
        indexes = bytes(image.get_flattened_data())
    assert fnv1a64(indexes) == native["after"]["images"][0]["content"]
    assert set(_pixels(destination)) <= {(0, 0, 0, 255), (255, 255, 255, 255)}
    assert set(indexes) == {1, 2}

    if algorithm == "ordered":
        conversion["target"]["dithering"]["matrix"] = {
            "kind": "file",
            "path": native["dithering"]["matrix"]["resolved_path"],
        }
        explicit = tmp_path / "file-matrix.png"
        _export(
            _request(
                source,
                explicit,
                color_mode=conversion,
                palette_preparation={"kind": "current"},
            )
        )
        with Image.open(explicit) as image:
            assert bytes(image.get_flattened_data()) == indexes
        assert _pixels(explicit) == _pixels(destination)
    assert source.read_bytes() == before


@pytest.mark.parametrize("preparation", ("current", "quantize"))
def test_palette_preparation_uses_only_selected_frame_and_rectangle(
    tmp_path: Path, preparation: str
) -> None:
    source = _source(tmp_path, scenario="selection")
    selected_palette = [
        (0, 0, 0, 0),
        (70, 70, 70, 255),
        (130, 130, 130, 255),
        (240, 240, 240, 128),
    ]
    inject_palette_change(source, selected_palette, frame_number=2)
    before = source.read_bytes()
    palette: dict = {"kind": preparation}
    if preparation == "quantize":
        palette.update(
            max_colors=3,
            with_alpha=True,
            rgb_map_algorithm="octree",
            new_layer_blending_method=True,
        )
    destination = tmp_path / "selected.png"
    result = _export(
        _request(
            source,
            destination,
            frame_number=2,
            export_image_area={
                "kind": "rectangle",
                "rectangle": {"x": 2, "y": 0, "width": 2, "height": 1},
            },
            color_mode=conversion_for("rgb", "indexed"),
            palette_preparation=palette,
        )
    )

    assert _pixels(destination) == [(70, 70, 70, 255), (130, 130, 130, 255)]
    assert (result["width"], result["height"]) == (2, 1)
    entries = [
        (entry["red"], entry["green"], entry["blue"], entry["alpha"])
        for entry in result["palette_entries"]
    ]
    if preparation == "current":
        assert entries == selected_palette
        with Image.open(destination) as image:
            assert list(image.get_flattened_data()) == [1, 2]
    else:
        assert len(entries) <= 3
        opaque = {entry for entry in entries if entry[3] == 255}
        assert opaque == {(70, 70, 70, 255), (130, 130, 130, 255)}
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    ("fault", "code"),
    (
        ("wrong_mode", "color_mode_mismatch"),
        ("missing_matrix", "dithering_matrix_invalid"),
    ),
)
def test_conversion_refusal_preserves_source_and_existing_destination(
    tmp_path: Path, fault: str, code: str
) -> None:
    source = _source(tmp_path)
    before = source.read_bytes()
    destination = tmp_path / "preserved.png"
    destination.write_bytes(b"existing destination")
    conversion = conversion_for("indexed", "rgb")
    choices: dict = {}
    if fault == "missing_matrix":
        conversion = conversion_for("rgb", "indexed")
        conversion["target"]["dithering"] = {
            "algorithm": "ordered",
            "matrix": {"kind": "installed", "id": "missing-export-matrix"},
        }
        choices["palette_preparation"] = {"kind": "current"}
    request = _request(
        source,
        destination,
        color_mode=conversion,
        **choices,
    )
    request["destination"]["if_exists"] = "replace"
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode != 0, run.stdout
    failure = json.loads(run.stdout)
    assert failure["code"] == code, failure
    if fault == "wrong_mode":
        assert failure["details"]["expected"] == "indexed"
        assert failure["details"]["actual"] == "rgb"
    else:
        assert failure["details"]["reason"] == "missing"
        assert (
            failure["details"]["matrix"] == conversion["target"]["dithering"]["matrix"]
        )
    assert destination.read_bytes() == b"existing destination"
    assert source.read_bytes() == before
    assert not list(tmp_path.glob("*.staged.*"))


@pytest.mark.parametrize("mode", MODES)
def test_background_preserves_opaque_samples_and_fills_transparency(
    tmp_path: Path, mode: str
) -> None:
    source = _source(tmp_path, mode)
    before = source.read_bytes()
    background = {
        "rgb": {"kind": "rgba", "red": 33, "green": 33, "blue": 33, "alpha": 255},
        "grayscale": {"kind": "grayscale", "gray": 33, "alpha": 255},
        "indexed": {"kind": "palette-index", "index": 2},
    }[mode]
    destination = tmp_path / "opaque.png"
    result = _export(
        _request(
            source,
            destination,
            transparency={"kind": "background", "background_color": background},
        )
    )
    gray = 180 if mode == "indexed" else 33
    assert _pixels(destination) == [(90, 90, 90, 255), (gray, gray, gray, 255)]
    assert result["effective_background"] is True
    assert (
        result["alpha_channel"]["minimum"] == result["alpha_channel"]["maximum"] == 255
    )
    assert source.read_bytes() == before


def test_indexed_background_refuses_used_palette_alpha_128_without_publication(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path, "indexed", "semi")
    before = source.read_bytes()
    destination = tmp_path / "preserved.png"
    destination.write_bytes(b"existing destination")
    request = _request(
        source,
        destination,
        transparency={
            "kind": "background",
            "background_color": {"kind": "palette-index", "index": 2},
        },
    )
    request["destination"]["if_exists"] = "replace"
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode != 0, run.stdout
    failure = json.loads(run.stdout)
    assert failure["code"] == "export_image_invalid", failure
    assert failure["details"]["reason"] == "background"
    assert destination.read_bytes() == b"existing destination"
    assert source.read_bytes() == before
    assert not list(tmp_path.glob("*.staged.*"))
