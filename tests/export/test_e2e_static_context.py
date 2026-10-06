"""Static export preserves native editor context and Source on late failures."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.aseprite import aseprite
from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png_input import decode_png_artifact
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.ports import OperationServices
from spa.contracts.public import RuntimeRequest
from spa.delivery.export import EXPORT_OPERATIONS
from tests.export.support import export_image_request as _request
from tests.export.support import source_sprite

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def runtime():
    return aseprite.probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


@pytest.mark.parametrize("fault", ["success", "after_palette", "encode"])
def test_export_restores_editor_and_source_after_native_color_operations(
    tmp_path: Path, runtime, monkeypatch, fault: str
) -> None:
    source = source_sprite(tmp_path, "group_composition.lua")
    original = source.read_bytes()
    destination = tmp_path / "image.png"
    previous_artifact = b"existing destination must survive failure"
    destination.write_bytes(previous_artifact)
    context_report = tmp_path / "context.json"
    original_run = aseprite._run
    launches = []

    def context_launch(
        command, environment, timeout, canonical, *, working_directory=None
    ):
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
            str(Path(__file__).parent / "fixtures/static_context.lua"),
        ]
        return original_run(
            command,
            environment,
            timeout,
            canonical,
            working_directory=working_directory,
        )

    monkeypatch.setattr(aseprite, "_run", context_launch)
    request = _request(source, destination) | {
        "destination": {"path": str(destination), "if_exists": "replace"},
        "layer_composition": {
            "mode": "include",
            "layers": [{"layer_name": "hidden red"}],
        },
        "color_profile": {"kind": "assign", "profile": {"kind": "none"}},
        "palette_preparation": {
            "kind": "quantize",
            "max_colors": 4,
            "with_alpha": True,
            "rgb_map_algorithm": "octree",
            "new_layer_blending_method": False,
        },
        "color_mode": {
            "source_color_mode": "rgb",
            "target": {
                "color_mode": "indexed",
                "rgb_map_algorithm": "octree",
                "color_best_fit_criteria": "rgb",
                "dithering": {"algorithm": "none"},
            },
        },
    }
    services = OperationServices(
        probe_runtime=lambda _: runtime,
        invoke_kernel=aseprite.invoke,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
        decode_png_artifact=decode_png_artifact,
    )
    result = dispatch(
        EXPORT_OPERATIONS[0], json.dumps(request), {}, services, FAILURE_CODES
    ).model_dump(mode="json")
    assert len(launches) == 1
    assert context_report.is_file(), result
    context = json.loads(context_report.read_text())
    for name in (
        "active_sprite_restored",
        "active_layer_restored",
        "active_frame_restored",
        "foreground_restored",
        "background_restored",
        "compose_groups_restored",
        "blend_preference_restored",
        "opened_sprites_released",
        "ambient_preserved",
        "source_preserved",
        "pipeline_source_preserved",
        "profile_applied",
        "palette_prepared",
    ):
        assert context[name] is True, context
    assert context["source_snapshot_count"] == 2
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".*.staged*"))
    if fault == "success":
        assert result["status"] == "success", result
        assert result["color_mode"] == "indexed"
        assert result["color_profile"] == "none"
        assert context["fault_injected"] is False
        assert destination.read_bytes() != previous_artifact
        with Image.open(destination) as image:
            assert image.mode == "P" and image.size == (1, 1)
    else:
        assert result["code"] == "kernel_execution_failed", result
        assert context["fault_injected"] is True
        assert destination.read_bytes() == previous_artifact
        assert "injected static export" in result["details"]["reason"]
        assert context["rgba_written_during_fault"] is (fault == "encode")
