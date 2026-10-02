"""Installed CLI tests against a real Aseprite executable."""

import json
import os
import sys
from pathlib import Path

import pytest
from jsonschema import validate

from tests.support import spa

pytestmark = pytest.mark.e2e


def test_info_reports_installed_runtime() -> None:
    run = spa("info", "--aseprite", os.environ["SPA_TEST_ASEPRITE"], "--json")
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["operation"] == "spa info"
    assert result["runtime"]["resource_complete"] is True
    # Pin the evidence profile without using the product version as a runtime gate.
    assert result["runtime"]["aseprite_version"].startswith("1.3.18.5")
    assert result["runtime"]["api_version"] == 41
    assert result["runtime"]["lua_version"] == "Lua 5.4"
    assert result["runtime"]["verified_prerequisites"] == [
        "aseprite_scripting",
        "lua_file_io",
        "aseprite_json",
    ]
    conversion_available = (
        "aseprite_convert_color_profile" in result["runtime"]["verified_capabilities"]
    )
    # Current Linux LAF_BACKEND=none has no native color converter.
    assert conversion_available or sys.platform == "linux"
    expected_runtime = [
        "aseprite_runtime_introspection",
        "aseprite_paint_composite",
        "aseprite_paint_composite_indexed",
        "aseprite_selection",
        "aseprite_filter_brightness_contrast",
        "aseprite_filter_hue_saturation",
        "aseprite_change_color_mode",
        "aseprite_assign_color_profile",
        "aseprite_convert_color_profile",
        "aseprite_palette_entries",
        "aseprite_palette_files",
        "aseprite_palette_quantization",
        "aseprite_palette_resize",
        "aseprite_palette_remap",
        "aseprite_palette_reorder",
        "aseprite_sprite_create",
        "aseprite_sprite_inspection",
        "aseprite_sprite_flatten",
        "aseprite_sprite_resize",
        "aseprite_image_canvas_transform",
        "aseprite_image_resize",
        "aseprite_image_snapshot",
        "aseprite_image_flip",
        "aseprite_image_rotate",
        "aseprite_sprite_crop",
        "aseprite_layer_hierarchy",
        "aseprite_layer_mutation",
        "aseprite_layer_merge",
        "aseprite_background_conversion",
        "aseprite_paint_fill",
        "aseprite_paint_line",
        "aseprite_paint_pencil",
        "aseprite_paint_pencil_regular",
        "aseprite_paint_pencil_pixel_perfect",
        "aseprite_paint_pencil_dots",
        "aseprite_paint_eraser",
        "aseprite_paint_eraser_regular",
        "aseprite_paint_eraser_pixel_perfect",
        "aseprite_paint_eraser_dots",
        "aseprite_paint_rectangle",
        "aseprite_paint_ellipse",
        "aseprite_paint_contour",
        "aseprite_paint_blur",
        "aseprite_paint_apply",
        "aseprite_frame_authoring",
        "aseprite_frame_editing",
        "aseprite_cel_lifecycle",
        "aseprite_cel_relationships",
        "aseprite_tag_authoring",
        "aseprite_export_image",
    ]
    if not conversion_available:
        expected_runtime.remove("aseprite_convert_color_profile")
    assert result["runtime"]["verified_capabilities"] == expected_runtime
    expected_operations = [
        "spa info",
        "spa version",
        "spa schema",
        "spa sprite create",
        "spa sprite get",
        "spa sprite copy",
        "spa sprite flatten",
        "spa sprite resize",
        "spa sprite crop",
        "spa sprite validate",
        "spa layer list",
        "spa layer get",
        "spa layer add",
        "spa layer set",
        "spa layer move",
        "spa layer remove",
        "spa layer merge",
        "spa layer convert-to-background",
        "spa layer convert-from-background",
        "spa paint apply",
        "spa paint composite",
        "spa paint fill",
        "spa paint eraser",
        "spa paint pencil",
        "spa paint line",
        "spa paint rectangle",
        "spa paint ellipse",
        "spa paint contour",
        "spa paint blur",
        "spa filter brightness-contrast",
        "spa filter hue-saturation",
        "spa selection create",
        "spa selection combine",
        "spa selection invert",
        "spa selection grow",
        "spa selection shrink",
        "spa selection transform",
        "spa selection validate",
        "spa selection export",
        "spa selection preview",
        "spa frame list",
        "spa frame get",
        "spa frame add",
        "spa frame duplicate",
        "spa frame set",
        "spa frame move",
        "spa frame remove",
        "spa cel list",
        "spa cel get",
        "spa cel add",
        "spa cel clear",
        "spa cel remove",
        "spa cel set",
        "spa cel copy",
        "spa cel link",
        "spa cel unlink",
        "spa motion apply",
        "spa image resize",
        "spa image get",
        "spa image replace",
        "spa image crop",
        "spa image canvas-resize",
        "spa image flip",
        "spa image rotate",
        "spa tag list",
        "spa tag get",
        "spa tag add",
        "spa tag set",
        "spa tag remove",
        "spa palette reorder",
        "spa palette remap",
        "spa palette resize",
        "spa palette list",
        "spa palette get",
        "spa palette set",
        "spa palette import",
        "spa palette color-quantization",
        "spa sprite change-color-mode",
        "spa sprite assign-color-profile",
        "spa sprite convert-color-profile",
        "spa export image",
        "spa palette export",
        "spa animation audit",
        "spa animation compare",
        "spa animation preview",
        "spa plan check",
        "spa plan run",
    ]
    expected_runtime_gaps = []
    if not conversion_available:
        # Plan discovery conservatively requires all eligible Step capabilities.
        expected_runtime_gaps = ["spa sprite convert-color-profile", "spa plan run"]
        for operation in expected_runtime_gaps:
            expected_operations.remove(operation)
    assert result["supported_capabilities"] == expected_operations
    assert [
        gap["capability"] for gap in result["capability_gaps"]
    ] == expected_runtime_gaps + [
        f"spa paint composite: grayscale {mode}"
        for mode in ("hue", "saturation", "color", "luminosity", "addition")
    ] + [
        "spa paint composite: indexed blend-mode/opacity",
        "Paint Dynamics",
        "Image Brush",
        "shading Ink",
        "spa paint gradient",
        "spa paint contour: Paint Dynamics",
        "spa paint spray",
        "spa paint curve",
        "spa paint polygon",
        "spa paint jumble",
        "spa palette add",
        "spa palette remove",
        "spa filter brightness-contrast: Tilemap pixels",
        "spa filter hue-saturation: Tilemap pixels",
    ]
    assert all(
        gap["aseprite_version"] == result["runtime"]["aseprite_version"]
        and gap["evidence"]
        for gap in result["capability_gaps"]
    )
    info_schema = json.loads(spa("info", "--schema").stdout)
    validate(result, info_schema["result_schema"])
    input_run = spa(
        "info",
        "--input-json",
        json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert input_run.returncode == 0, input_run.stdout
    assert json.loads(input_run.stdout)["runtime"] == result["runtime"]
    human_run = spa("info", "--aseprite", os.environ["SPA_TEST_ASEPRITE"], "--human")
    assert human_run.returncode == 0, human_run.stdout
    assert "Lua 5.4" in human_run.stdout


def test_symlinked_executable_resolves_to_resource_complete_bundle(
    tmp_path: Path,
) -> None:
    link = tmp_path / "aseprite"
    link.symlink_to(os.environ["SPA_TEST_ASEPRITE"])
    run = spa("info", "--aseprite", str(link))
    assert run.returncode == 0, run.stdout
    runtime = json.loads(run.stdout)["runtime"]
    assert runtime["requested_path"] == str(link)
    assert runtime["discovered_path"] == str(link)
    assert runtime["canonical_path"] == str(
        Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    )


@pytest.mark.skipif(
    sys.platform != "darwin"
    or not os.environ.get("SPA_TEST_ASEPRITE")
    or os.environ.get("SPA_TEST_MACOS_AGENT_SANDBOX") != "1",
    reason="requires installed Aseprite in a macOS agent sandbox",
)
def test_macos_agent_sandbox_starts_installed_aseprite_script() -> None:
    executable = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    assert executable.parent.name == "MacOS"
    assert executable.parent.parent.name == "Contents"
    assert executable.parent.parent.parent.suffix == ".app"

    run = spa("info", "--aseprite", str(executable), "--json")
    assert run.returncode == 0, run.stdout
    result = json.loads(run.stdout)
    validate(result, json.loads(spa("info", "--schema").stdout)["result_schema"])
    assert result["runtime"]["canonical_path"] == str(executable)
    assert result["runtime"]["resource_complete"] is True
