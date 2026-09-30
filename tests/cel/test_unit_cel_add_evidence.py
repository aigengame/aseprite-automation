"""A contradictory Add receipt cannot publish a staged file."""

from pathlib import Path

import pytest

from spa.adapters.files import LocalTargetFiles
from spa.application.plan import PlanRunRequest, run_plan
from spa.authoring.document.cel import CelAddRequest, add_cel
from spa.contracts.ports import KernelInvocationResult, OperationServices, RuntimeIssue
from spa.contracts.public import Diagnostics
from tests.support import runtime_observation


@pytest.mark.parametrize("plan", [False, True])
@pytest.mark.parametrize("image_size", [None, {"width": 5, "height": 5}])
def test_wrong_image_geometry_is_rejected_before_commit(
    tmp_path: Path, plan: bool, image_size: dict | None
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    source.write_bytes(b"Source")
    target.write_bytes(b"prior Target")
    bounds = {"x": 0, "y": 0, "width": 2, "height": 2}
    before = {
        "layer_path": [1],
        "frame_number": 1,
        "exists": False,
        "content": "absent",
        "is_background": False,
        "is_tilemap": False,
        "position": None,
        "image_bounds": None,
        "opacity": None,
        "z_index": None,
        "linked_cels": [],
    }
    after = before | {
        "exists": True,
        "content": "transparent",
        "image_bounds": bounds,
        "position": {"x": 0, "y": 0},
        "opacity": 255,
        "z_index": 0,
    }
    # The returned Cel and final inspection agree with each other but both
    # contradict the requested size (or the default 4x3 Canvas).
    sprite = {
        "metadata": {
            "width": 4,
            "height": 3,
            "color_mode": "rgb",
            "frame_count": 1,
            "tag_count": 0,
            "palette_count": 0,
            "layer_count": 1,
            "cel_count": 1,
            "slice_count": 0,
            "tileset_count": 0,
            "transparent_color_index": 0,
            "grid_bounds": {"x": 0, "y": 0, "width": 1, "height": 1},
            "pixel_ratio": {"width": 1, "height": 1},
            "use_layer_uuids": False,
        },
        "frames": [{"frame_number": 1, "duration_ms": 100}],
        "tags": [],
        "palettes": [],
        "slices": [],
        "tilesets": [],
        "layers": [
            {
                "path": [1],
                "name": "Layer",
                "layer_uuid": None,
                "opacity": 255,
                "blend_mode": "normal",
                "is_image": True,
                "is_group": False,
                "is_tilemap": False,
                "is_reference": False,
                "is_visible": True,
                "is_editable": True,
                "is_continuous": False,
                "is_collapsed": False,
                "is_transparent": True,
                "is_background": False,
                "children": [],
            }
        ],
        "cels": [
            {
                "layer_path": [1],
                "frame_number": 1,
                "bounds": bounds,
                "opacity": 255,
                "z_index": 0,
            }
        ],
    }
    receipt = {"before": before, "before_cel_count": 0, "cel": after}
    response = (
        {"steps": [{"operation": "cel add", "result": receipt}], "final_sprite": sprite}
        if plan
        else receipt | {"sprite": sprite}
    ) | {"persisted_reopen_verified": True}

    def invoke(_runtime, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"unverified staged bytes")
        return KernelInvocationResult(
            response, "/response.json", Diagnostics(exit_status=0)
        )

    services = OperationServices(
        probe_runtime=lambda _request: runtime_observation(),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        invoke_kernel_direct=invoke,
    )
    cel_input = {
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "image_size": image_size,
    }
    files = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
    }
    with pytest.raises(RuntimeIssue) as failure:
        if plan:
            run_plan(
                PlanRunRequest.model_validate(
                    {
                        "plan": {
                            **files,
                            "steps": [{"operation": "cel add", "input": cel_input}],
                        }
                    }
                ),
                services,
            )
        else:
            add_cel(CelAddRequest.model_validate(files | cel_input), services)
    assert failure.value.kind == "postcondition_failed"
    if plan:
        assert failure.value.evidence.failed_step == 1
    assert source.read_bytes() == b"Source"
    assert target.read_bytes() == b"prior Target"
    assert not list(tmp_path.glob("*.staged.aseprite"))
