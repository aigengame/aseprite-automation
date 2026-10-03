"""Native context restoration and real save/reopen failures for PNG import."""

import json
from importlib.resources import files
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from spa.adapters.aseprite import aseprite
from spa.adapters.png_input import decode_png_input
from spa.contracts.digest import fnv1a64

from .test_e2e_image_import import _create
from .test_e2e_image_import import runtime as runtime  # noqa: PLC0414
from .test_e2e_import_boundaries import (
    _assert_unpublished,
    _dispatch,
    _inputs,
    _ObservedTargetFiles,
)

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize(
    "profile_name,fault",
    [
        ("none", "success"),
        ("srgb", "success"),
        ("linear_srgb", "success"),
        ("none", "refusal"),
        ("none", "post_mutation"),
        ("none", "reopen_loss"),
    ],
)
def test_import_restores_native_context_and_preserves_encoded_meaning(
    tmp_path, runtime, monkeypatch, profile_name, fault
):
    source, raster, target = _inputs(tmp_path, runtime, indexed=fault == "refusal")
    if profile_name != "none":
        kwargs = {}
        if profile_name == "srgb":
            _create(runtime, source, profile="srgb")
            info = PngInfo()
            info.add(b"sRGB", b"\0")
            kwargs["pnginfo"] = info
        else:
            icc = files("spa.kernel").joinpath("color/profiles/linear_srgb.icc")
            _create(runtime, source, profile="icc", icc=str(icc))
            kwargs["icc_profile"] = icc.read_bytes()
        Image.new("RGBA", (2, 1), (17, 31, 53, 128)).save(raster, **kwargs)
        target.write_bytes(source.read_bytes())
    elif fault == "refusal":
        # Leave an Indexed target but consume an RGB PNG: native refusal.
        Image.new("RGBA", (2, 1), (17, 31, 53, 128)).save(raster)
    original = source.read_bytes(), raster.read_bytes(), target.read_bytes()
    observed_files = _ObservedTargetFiles()
    context_report = tmp_path / "context.json"
    original_run = aseprite._run
    launches = []

    def context_launch(command, environment, timeout, canonical):
        assert command[-2] == "--script"
        launches.append(command[-1])
        command = [
            *command[:-2],
            "--script-param",
            f"production_handler={command[-1]}",
            "--script-param",
            f"context_report={context_report}",
            "--script-param",
            f"fault={fault}",
            "--script",
            str(Path(__file__).parent / "fixtures/import_context.lua"),
        ]
        return original_run(command, environment, timeout, canonical)

    monkeypatch.setattr(aseprite, "_run", context_launch)
    result = _dispatch(source, raster, target, runtime, observed_files, aseprite.invoke)
    assert len(launches) == 1
    assert context_report.is_file(), result
    context = json.loads(context_report.read_text())
    for name in (
        "active_sprite_restored",
        "active_layer_restored",
        "active_frame_restored",
        "ambient_pixels_preserved",
        "opened_sprites_released",
    ):
        assert context[name] is True, context
    assert context["preferences_before"] == context["preferences_after"]
    assert context["preferences_before"]["files_with_profile"] == 2
    assert context["preferences_before"]["missing_profile"] == 3
    if fault == "success":
        assert result["status"] == "success", result
        assert result["color_profile"]["kind"] == (
            "icc" if profile_name == "linear_srgb" else profile_name
        )
        assert result["image"]["rgba_content_digest"]["value"] == fnv1a64(
            decode_png_input(original[1]).rgba_bytes
        )
        assert (source.read_bytes(), raster.read_bytes()) == original[:2]
        assert (
            observed_files.commits == observed_files.stages == observed_files.discards
        )
        assert all(not stage.exists() for stage in observed_files.stages)
    else:
        expected = (
            "image_import_incompatible"
            if fault == "refusal"
            else "kernel_execution_failed"
        )
        assert result.get("code") == expected, result
        assert not observed_files.commits
        _assert_unpublished(source, raster, target, original, observed_files)
        if fault == "refusal":
            assert result["details"]["reason"] == "color_mode"
            assert context["fault_injected"] is False
        else:
            assert context["fault_injected"] is True
            if fault == "post_mutation":
                assert (
                    "injected error after native newCel" in result["details"]["reason"]
                )
            else:
                assert context["stage_written"] is True
                assert context["before_pixel"] != context["after_pixel"]
                assert "Persisted profile Images differs" in result["details"]["reason"]
