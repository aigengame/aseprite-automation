"""Static PNG Profile choices and native Profile-before-Palette operation order."""

import json
import os
from importlib.resources import files
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.aseprite.aseprite import probe
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.export.support import export_image_request as _request
from tests.export.support import png_icc_label, source_sprite
from tests.export.test_e2e_static_geometry import _export
from tests.support import spa

pytestmark = pytest.mark.e2e
PROFILES = ("none", "srgb", "linear_srgb", "display_p3")
UNCHANGED = [(11, 22, 33, 255), (44, 55, 66, 255)]


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


def _icc(identity: str) -> Path:
    return Path(str(files("spa.kernel").joinpath(f"color/profiles/{identity}.icc")))


def _profile(identity: str) -> dict:
    return (
        {"kind": identity}
        if identity in ("none", "srgb")
        else {"kind": "icc", "icc_file": str(_icc(identity))}
    )


def _source(tmp_path: Path, identity: str, *, mode: str = "rgb") -> Path:
    return source_sprite(
        tmp_path,
        "rgb_profile_alpha.lua",
        mode=mode,
        alpha="opaque",
        profile=identity if identity in ("none", "srgb") else "icc",
        icc_file=str(_icc(identity)),
    )


def _encoded_profile(result: dict, destination: Path, identity: str) -> None:
    with Image.open(destination) as image:
        if identity in ("none", "srgb"):
            assert result["color_profile"] == identity
            assert result["icc_identity"] is None
            assert "icc_profile" not in image.info
            assert image.info.get("srgb") == (0 if identity == "srgb" else None)
        else:
            assert (
                result["color_profile"] == "icc" and result["icc_identity"] == identity
            )
            assert image.info["icc_profile"] == _icc(identity).read_bytes()
            assert png_icc_label(destination.read_bytes()) == identity.encode("ascii")


@pytest.mark.parametrize("identity", PROFILES)
def test_preserve_keeps_profile_encoding_and_stored_channels(
    tmp_path: Path, identity: str
) -> None:
    source = _source(tmp_path, identity)
    before = source.read_bytes()
    destination = tmp_path / "preserved.png"
    result = _export(_request(source, destination))
    _encoded_profile(result, destination, identity)
    with Image.open(destination) as image:
        assert list(image.convert("RGBA").get_flattened_data()) == UNCHANGED
    assert source.read_bytes() == before


@pytest.mark.parametrize("identity", PROFILES)
def test_assign_changes_only_profile_and_preserves_stored_channels(
    tmp_path: Path, identity: str
) -> None:
    source = _source(tmp_path, "srgb" if identity == "none" else "none")
    before = source.read_bytes()
    destination = tmp_path / "assigned.png"
    result = _export(
        _request(
            source,
            destination,
            color_profile={"kind": "assign", "profile": _profile(identity)},
        )
    )
    _encoded_profile(result, destination, identity)
    with Image.open(destination) as image:
        assert list(image.convert("RGBA").get_flattened_data()) == UNCHANGED
    assert source.read_bytes() == before


def _conversion_refusal(
    run, runtime, source: Path, before: bytes, destination: Path, prior: bytes
) -> bool:
    if "aseprite_convert_color_profile" in runtime.verified_capabilities:
        return False
    assert run.returncode != 0
    failure = json.loads(run.stdout)
    assert failure["code"] == "runtime_incompatible", failure
    assert (
        "aseprite_convert_color_profile" in failure["details"]["missing_capabilities"]
    )
    assert source.read_bytes() == before and destination.read_bytes() == prior
    return True


@pytest.mark.parametrize(
    ("source_profile", "target_profile", "pixels"),
    [
        ("none", "srgb", UNCHANGED),
        ("srgb", "srgb", UNCHANGED),
        ("srgb", "linear_srgb", [(1, 2, 4, 255), (6, 10, 14, 255)]),
        ("linear_srgb", "srgb", [(59, 83, 101, 255), (115, 128, 139, 255)]),
        ("linear_srgb", "linear_srgb", UNCHANGED),
        ("display_p3", "srgb", [(8, 22, 34, 255), (41, 55, 67, 255)]),
        ("display_p3", "display_p3", UNCHANGED),
    ],
)
def test_each_admitted_profile_conversion_uses_actual_runtime_capability(
    tmp_path: Path, runtime, source_profile: str, target_profile: str, pixels: list
) -> None:
    source = _source(tmp_path, source_profile)
    before = source.read_bytes()
    destination = tmp_path / "converted.png"
    prior = b"existing destination"
    destination.write_bytes(prior)
    request = _request(
        source,
        destination,
        color_profile={"kind": "convert", "profile": _profile(target_profile)},
    )
    request["destination"]["if_exists"] = "replace"
    run = spa("export", "image", "--input-json", json.dumps(request))
    if _conversion_refusal(run, runtime, source, before, destination, prior):
        return
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    _encoded_profile(result, destination, target_profile)
    with Image.open(destination) as image:
        assert list(image.convert("RGBA").get_flattened_data()) == pixels
    assert source.read_bytes() == before


def test_unadmitted_srgb_to_display_p3_direction_preserves_existing_destination(
    tmp_path: Path, runtime
) -> None:
    source = _source(tmp_path, "srgb")
    before = source.read_bytes()
    destination = tmp_path / "refused.png"
    prior = b"existing destination"
    destination.write_bytes(prior)
    request = _request(
        source,
        destination,
        color_profile={"kind": "convert", "profile": _profile("display_p3")},
    )
    request["destination"]["if_exists"] = "replace"
    run = spa("export", "image", "--input-json", json.dumps(request))
    if _conversion_refusal(run, runtime, source, before, destination, prior):
        return
    assert run.returncode != 0
    failure = json.loads(run.stdout)
    assert failure["code"] == "color_profile_file_failed", failure
    assert failure["details"]["reason"] == "unsupported_conversion"
    assert source.read_bytes() == before and destination.read_bytes() == prior


@pytest.mark.parametrize("profile_choice", ["preserve", "assign"])
def test_grayscale_with_rgb_icc_profile_refuses_publication(
    tmp_path: Path, profile_choice: str
) -> None:
    source = _source(
        tmp_path,
        "linear_srgb" if profile_choice == "preserve" else "srgb",
        mode="grayscale",
    )
    before = source.read_bytes()
    destination = tmp_path / "gray.png"
    request = _request(
        source,
        destination,
        color_profile="preserve"
        if profile_choice == "preserve"
        else {"kind": "assign", "profile": _profile("linear_srgb")},
    )
    run = spa("export", "image", "--input-json", json.dumps(request))
    assert run.returncode != 0
    failure = json.loads(run.stdout)
    assert failure["code"] == "export_image_invalid", failure
    assert failure["details"]["reason"] == "color_profile"
    assert not destination.exists() and source.read_bytes() == before


@pytest.mark.parametrize("palette_format", ["gpl", "png"])
def test_profile_conversion_precedes_palette_import_and_mapping_on_selected_content(
    tmp_path: Path, runtime, palette_format: str
) -> None:
    source = source_sprite(
        tmp_path, "static_profiles_order.lua", icc_file=str(_icc("linear_srgb"))
    )
    before = source.read_bytes()
    palette = tmp_path / f"mapping.{palette_format}"
    entries = [
        (0, 0, 0, 0),
        (120, 120, 120, 255),
        (200, 200, 200, 255),
        (255, 255, 255, 255),
        (0, 0, 0, 255),
    ]
    if palette_format == "gpl":
        palette.write_text(
            "GIMP Palette\nChannels: RGBA\nName: ordered export\n#\n"
            + "".join(" ".join(map(str, color)) + " sample\n" for color in entries)
        )
    else:
        card = Image.new("P", (1, 1))
        card.putpalette(bytes(channel for color in entries for channel in color[:3]))
        card.save(palette, transparency=bytes(color[3] for color in entries))
    destination = tmp_path / "ordered.png"
    prior = b"existing destination"
    destination.write_bytes(prior)
    request = _request(
        source,
        destination,
        frame_number=2,
        export_image_area={
            "kind": "rectangle",
            "rectangle": {"x": 1, "y": 0, "width": 3, "height": 1},
        },
        layer_composition={"mode": "include", "layers": [{"layer_name": "sample"}]},
        color_profile={"kind": "convert", "profile": {"kind": "srgb"}},
        palette_preparation={
            "kind": "import",
            "palette_file": {"format": palette_format, "path": str(palette)},
        },
        color_mode={
            "source_color_mode": "rgb",
            "target": {
                "color_mode": "indexed",
                "rgb_map_algorithm": "default",
                "color_best_fit_criteria": "default",
                "dithering": {"algorithm": "none"},
            },
        },
    )
    request["destination"]["if_exists"] = "replace"
    run = spa("export", "image", "--input-json", json.dumps(request))
    if _conversion_refusal(run, runtime, source, before, destination, prior):
        return
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["frame_number"] == 2 and result["resolved_layer_paths"] == [[1]]
    assert result["palette_entries"] == [
        dict(zip(("red", "green", "blue", "alpha"), color)) for color in entries
    ]
    _encoded_profile(result, destination, "srgb")
    with Image.open(destination) as image:
        assert image.mode == "P" and image.size == (3, 1)
        # Linear sample 100 becomes 168 before mapping. It maps to 200 (index 2);
        # mapping the unconverted sample would choose 120 (index 1).
        assert list(image.get_flattened_data()) == [2, 4, 3]
        assert list(image.convert("RGBA").get_flattened_data()) == [
            (200, 200, 200, 255),
            (0, 0, 0, 255),
            (255, 255, 255, 255),
        ]
    assert source.read_bytes() == before
