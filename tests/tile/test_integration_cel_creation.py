"""Tilemap creation receipts gate publication through both public entry points."""

from pathlib import Path

import pytest

from spa.adapters.files import LocalTargetFiles
from spa.application.plan import PlanRunRequest, run_plan
from spa.authoring.document.cel import CelAddRequest, add_cel
from spa.contracts.ports import KernelInvocationResult, OperationServices, RuntimeIssue
from spa.contracts.public import Diagnostics
from tests.support import runtime_observation


def _creation_response(plan: bool) -> dict:
    layer = {"layer_path": [1], "layer_uuid": None, "name": "map"}
    grid = {"origin": {"x": 0, "y": 0}, "tile_size": {"width": 2, "height": 3}}
    coverage = {"x": 0, "y": 0, "width": 4, "height": 9}
    before = {
        "layer_path": [1],
        "frame_number": 1,
        "exists": False,
        "content": "absent",
        "is_background": False,
        "is_tilemap": True,
        "position": None,
        "image_bounds": None,
        "opacity": None,
        "z_index": None,
        "linked_cels": [],
    }
    receipt = {
        "before": before,
        "before_cel_count": 0,
        "cel": before
        | {
            "exists": True,
            "content": "transparent",
            "position": {"x": 0, "y": 0},
            "opacity": 255,
            "z_index": 0,
        },
        "tilemap_creation": {
            "tilemap": {
                "layer": layer,
                "tileset_index": 1,
                "frame_number": 1,
                "exists": True,
                "position": {"x": 0, "y": 0},
                "cell_size": {"width": 2, "height": 3},
                "effective_grid": grid,
                "canvas_coverage": coverage,
            },
            "tileset": {
                "tileset_index": 1,
                "name": "terrain",
                "base_index": 1,
                "tile_count": 2,
                "grid": grid,
                "layers": [layer],
            },
            "empty_tile_cells_verified": True,
        },
    }
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
            "tileset_count": 1,
            "transparent_color_index": 0,
            "grid_bounds": {"x": 0, "y": 0, "width": 1, "height": 1},
            "pixel_ratio": {"width": 1, "height": 1},
            "use_layer_uuids": False,
        },
        "frames": [{"frame_number": 1, "duration_ms": 100}],
        "tags": [],
        "palettes": [],
        "slices": [],
        "tilesets": [
            {
                "name": "terrain",
                "tile_count": 2,
                "base_index": 1,
                "grid_origin": {"x": 0, "y": 0},
                "tile_size": {"width": 2, "height": 3},
            }
        ],
        "layers": [
            {
                "path": [1],
                "name": "map",
                "layer_uuid": None,
                "opacity": 255,
                "blend_mode": "normal",
                "is_image": True,
                "is_group": False,
                "is_tilemap": True,
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
                "bounds": coverage,
                "opacity": 255,
                "z_index": 0,
            }
        ],
    }
    return (
        {"steps": [{"operation": "cel add", "result": receipt}], "final_sprite": sprite}
        if plan
        else receipt | {"sprite": sprite}
    ) | {"persisted_reopen_verified": True}


def _run_creation(source: Path, target: Path, response: dict, plan: bool):
    def invoke(_runtime, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"verified staged bytes")
        return KernelInvocationResult(
            response, "/response.json", Diagnostics(exit_status=0)
        )

    services = OperationServices(
        probe_runtime=lambda _request: runtime_observation(
            "aseprite_tile_cel_creation"
        ),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        invoke_kernel_direct=invoke,
    )
    cel_input = {
        "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
        "tilemap_size": {"width": 2, "height": 3},
    }
    files = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": target.exists(),
    }
    if plan:
        return run_plan(
            PlanRunRequest.model_validate(
                {
                    "plan": files
                    | {"steps": [{"operation": "cel add", "input": cel_input}]}
                }
            ),
            services,
        )
    return add_cel(CelAddRequest.model_validate(files | cel_input), services)


@pytest.mark.parametrize("plan", [False, True])
@pytest.mark.parametrize("existing_target", [False, True])
def test_verified_tilemap_creation_publishes_target(
    tmp_path: Path, plan: bool, existing_target: bool
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"Source")
    if existing_target:
        target.write_bytes(b"prior Target")

    result = _run_creation(source, target, _creation_response(plan), plan)

    receipt = result.steps[0].result if plan else result
    assert receipt.cel.image_bounds is None
    assert receipt.tilemap_creation.tilemap.cell_size.model_dump() == {
        "width": 2,
        "height": 3,
    }
    assert receipt.tilemap_creation.tilemap.canvas_coverage.model_dump() == {
        "x": 0,
        "y": 0,
        "width": 4,
        "height": 9,
    }
    assert receipt.tilemap_creation.empty_tile_cells_verified is True
    assert result.target_commit.target_sprite_file == str(target)
    assert result.target_commit.byte_size == len(b"verified staged bytes")
    assert target.read_bytes() == b"verified staged bytes"
    assert source.read_bytes() == b"Source"
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.parametrize("plan", [False, True])
@pytest.mark.parametrize("existing_target", [False, True])
@pytest.mark.parametrize(
    "defect, failure_kind",
    [
        ("missing-tile-evidence", "postcondition_failed"),
        ("cell-size", "postcondition_failed"),
        ("grid-coverage", "postcondition_failed"),
        ("empty-proof-false", "response_malformed"),
        ("empty-proof-missing", "response_malformed"),
        ("frame", "postcondition_failed"),
        ("layer", "postcondition_failed"),
        ("linked-image", "postcondition_failed"),
        ("opacity", "postcondition_failed"),
    ],
)
def test_invalid_tilemap_creation_never_publishes(
    tmp_path: Path, plan: bool, existing_target: bool, defect: str, failure_kind: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"Source")
    if existing_target:
        target.write_bytes(b"prior Target")
    response = _creation_response(plan)
    receipt = response["steps"][0]["result"] if plan else response
    if defect == "missing-tile-evidence":
        receipt.pop("tilemap_creation")
    elif defect == "cell-size":
        receipt["tilemap_creation"]["tilemap"]["cell_size"]["width"] = 3
    elif defect == "grid-coverage":
        # The receipt and final inspection agree, but both contradict the Grid.
        receipt["tilemap_creation"]["tilemap"]["canvas_coverage"]["height"] = 8
    elif defect == "empty-proof-false":
        receipt["tilemap_creation"]["empty_tile_cells_verified"] = False
    elif defect == "empty-proof-missing":
        receipt["tilemap_creation"].pop("empty_tile_cells_verified")
    elif defect == "frame":
        receipt["tilemap_creation"]["tilemap"]["frame_number"] = 2
    elif defect == "layer":
        receipt["tilemap_creation"]["tilemap"]["layer"]["layer_path"] = [2]
    elif defect == "linked-image":
        receipt["cel"]["linked_cels"] = [{"layer_path": [1], "frame_number": 2}]
    elif defect == "opacity":
        receipt["cel"]["opacity"] = 128

    with pytest.raises(RuntimeIssue) as failure:
        _run_creation(source, target, response, plan)

    assert failure.value.kind == failure_kind
    if plan:
        assert failure.value.evidence.failed_step == 1
        assert failure.value.evidence.failed_operation == "cel add"
    assert source.read_bytes() == b"Source"
    if existing_target:
        assert target.read_bytes() == b"prior Target"
    else:
        assert not target.exists()
    assert set(tmp_path.iterdir()) == (
        {source, target} if existing_target else {source}
    )
