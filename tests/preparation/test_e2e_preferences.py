"""Preparation fixes effective choices and restores ambient native editor state."""

import json
import sys
from importlib.resources import files
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from spa.adapters.png_input import decode_png_input
from spa.contracts.ports import RuntimeObservation
from spa.preparation.contracts import (
    ExplicitCrop,
    PreparationSpecification,
    preparation_geometry,
)
from spa.preparation.raster import PREPARATION_HANDLER, NativePreparation
from tests.native_invocation import run, run_lua
from tests.preparation.support import specification
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("mode", ["rgba", "indexed"])
@pytest.mark.parametrize("source_kind", ["none", "srgb", "display_p3_cc0"])
def test_preparation_ignores_and_restores_editor_preferences(
    tmp_path: Path, runtime: RuntimeObservation, mode: str, source_kind: str
) -> None:
    source = tmp_path / "source.png"
    image = Image.new("RGBA", (3, 2))
    image.putdata(
        [
            (180, 70, 30, 255),
            (180, 70, 30, 255),
            (44, 11, 66, 0),
            (180, 70, 30, 127),
            (180, 70, 30, 128),
            (0, 0, 0, 0),
        ]
    )
    options = {}
    if source_kind == "srgb":
        metadata = PngImagePlugin.PngInfo()
        metadata.add(b"sRGB", bytes([3]))
        options["pnginfo"] = metadata
    elif source_kind == "display_p3_cc0":
        options["icc_profile"] = (
            files("spa.kernel")
            .joinpath("color/profiles/display_p3_cc0.icc")
            .read_bytes()
        )
    image.save(source, **options)
    original = source.read_bytes()
    spec = specification(mode)
    spec["palette"]["entries"] = [
        {"red": 0, "green": 0, "blue": 0, "alpha": 0},
        {"red": 180, "green": 70, "blue": 30, "alpha": 255},
        {"red": 195, "green": 60, "blue": 2, "alpha": 255},
    ]
    if source_kind == "display_p3_cc0" and (
        "aseprite_convert_color_profile" not in runtime.verified_capabilities
    ):
        # Exercise the actual public capability refusal on that Linux runtime.
        assert sys.platform == "linux", "Expected the proven native macOS converter"
        target = tmp_path / "refused.png"
        outcome = run(
            "raster prepare",
            {
                "raster_file": str(source),
                "intent": {"kind": "initial"},
                "specification": spec,
                "destination": {"path": str(target), "if_exists": "fail"},
            },
        )
        assert outcome.returncode != 0, process_diagnostics(outcome.process)
        failure = outcome.envelope
        assert failure["code"] == "runtime_incompatible", failure
        assert failure["details"]["missing_capabilities"] == [
            "aseprite_convert_color_profile"
        ]
        assert not target.exists() and source.read_bytes() == original
        return
    decoded = decode_png_input(original)
    declared = PreparationSpecification.model_validate(spec)
    assert isinstance(declared.crop, ExplicitCrop)
    geometry = preparation_geometry(declared, declared.crop.rectangle).model_dump()
    workspace = tmp_path / "native"
    workspace.mkdir()
    params = {
        "workspace": str(workspace),
        "aseprite_data": str(Path(runtime.resource_path).parent),
        "preparation_handler": str(
            files("spa.kernel").joinpath(PREPARATION_HANDLER.package_path)
        ),
        **{
            resource.parameter_name: str(
                files("spa.kernel").joinpath(resource.package_path)
            )
            for resource in PREPARATION_HANDLER.support_resources
        },
    }
    for number in (1, 2, 3):
        request = workspace / f"request-{number}.json"
        response = workspace / f"response-{number}.json"
        payload = {
            "raster_bytes": original.hex(),
            "decoded": {
                "width": decoded.width,
                "height": decoded.height,
                "rgba_bytes": decoded.rgba_bytes.hex(),
                "color_profile": decoded.color_profile,
                "icc_bytes": decoded.icc_bytes.hex() if decoded.icc_bytes else None,
            },
            "specification": declared.model_dump(),
            "geometry": geometry,
            "staged_png_file": str(workspace / f"output-{number}.png"),
            "staged_rgba_file": str(workspace / f"output-{number}.rgba"),
        }
        if number == 3:
            payload["decoded"]["rgba_bytes"] = "00" + decoded.rgba_bytes[1:].hex()
        request.write_text(
            json.dumps({"kernel_protocol_version": 1, "payload": payload})
        )
        prefix = f"request_{number}" if number < 3 else "refused_request"
        params[prefix] = str(request)
        prefix = f"response_{number}" if number < 3 else "refused_response"
        params[prefix] = str(response)
    lua = run_lua(
        Path(__file__).parent / "fixtures" / "preparation_preferences.lua",
        runtime,
        **params,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    observations = []
    expected = [(0, 0, 0, 0)] * 20
    color = (195, 60, 2, 255) if source_kind == "display_p3_cc0" else (180, 70, 30, 255)
    expected[6] = expected[7] = expected[12] = color
    for number in (1, 2):
        response = json.loads((workspace / f"response-{number}.json").read_text())
        assert response["status"] == "ok" and "rejection" not in response["result"], (
            response
        )
        native = NativePreparation.model_validate(response["result"])
        assert native.mapping.requested_rgb_map_algorithm == "octree"
        assert native.mapping.effective_rgb_map_algorithm == "octree"
        assert native.mapping.color_best_fit_criteria == "rgb"
        assert (
            native.dithering.requested_algorithm
            == native.dithering.effective_algorithm
            == "none"
        )
        assert native.profile.effective == "srgb" and native.normalized_alpha_preserved
        assert native.profile.converted == (source_kind == "display_p3_cc0")
        assert (
            native.source_rgba_digest != native.normalized_rgba_digest
        ) == native.profile.converted
        output = workspace / f"output-{number}.png"
        observed = decode_png_input(output.read_bytes())
        assert observed.color_type == (6 if mode == "rgba" else 3)
        assert observed.color_profile == "srgb" and observed.srgb_rendering_intent == 0
        assert observed.icc_bytes is None
        assert observed.rgba_bytes == (workspace / f"output-{number}.rgba").read_bytes()
        with Image.open(output) as rendered:
            assert list(rendered.convert("RGBA").get_flattened_data()) == expected
        observations.append((native.model_dump(), observed))
    assert observations[0] == observations[1]
    refusal = json.loads((workspace / "response-3.json").read_text())
    assert refusal["status"] == "ok"
    assert refusal["result"]["rejection"]["code"] == "preparation_rejected"
    assert refusal["result"]["rejection"]["details"]["reason"] == "native_input"
    assert not (workspace / "output-3.png").exists()
    assert source.read_bytes() == original
