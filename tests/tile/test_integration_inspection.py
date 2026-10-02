"""Reject malformed Kernel evidence before a JSON Snapshot becomes visible."""

import json
from pathlib import Path

import pytest

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.authoring.tile.inspection import TilemapGetRequest, get_tilemap
from spa.contracts.ports import KernelInvocationResult, OperationServices, RuntimeIssue
from spa.contracts.public import Diagnostics
from tests.support import runtime_observation


def _evidence(source: Path) -> dict:
    grid = {"origin": {"x": 0, "y": 0}, "tile_size": {"width": 2, "height": 3}}
    layer = {"layer_path": [2], "layer_uuid": None, "name": "map"}
    return {
        "sprite_file": str(source),
        "tileset": {
            "tileset_index": 1,
            "name": "terrain",
            "base_index": 1,
            "tile_count": 1,
            "grid": grid,
            "layers": [layer],
        },
        "tilemap": {
            "layer": layer,
            "tileset_index": 1,
            "frame_number": 1,
            "exists": True,
            "position": {"x": 0, "y": 0},
            "cell_size": {"width": 2, "height": 2},
            "effective_grid": grid,
            "canvas_coverage": {"x": 0, "y": 0, "width": 4, "height": 6},
        },
        "snapshot": None,
        "output_form": "artifact",
    }


@pytest.mark.parametrize(
    "defect",
    ["frame", "layer", "source", "region", "inline-and-artifact", "bad-rejection"],
)
def test_invalid_evidence_never_replaces_existing_artifact(
    tmp_path: Path, defect: str
) -> None:
    source, destination = tmp_path / "source.aseprite", tmp_path / "region.json"
    source.write_bytes(b"source")
    destination.write_bytes(b"previous artifact")
    request = TilemapGetRequest.model_validate(
        {
            "sprite_file": str(source),
            "target": {"layer": {"layer_path": [2]}, "frame_number": 1},
            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
            "snapshot_destination": {"path": str(destination), "if_exists": "replace"},
        }
    )
    evidence = _evidence(source)
    snapshot = {"rectangle": {"x": 0, "y": 0, "width": 1, "height": 1}, "entries": []}
    if defect == "frame":
        evidence["tilemap"]["frame_number"] = 2
    elif defect == "layer":
        evidence["tilemap"]["layer"]["layer_path"] = [3]
    elif defect == "source":
        evidence["sprite_file"] = "wrong.aseprite"
    elif defect == "region":
        snapshot["rectangle"]["x"] = 1
    elif defect == "inline-and-artifact":
        evidence["snapshot"] = snapshot
    else:
        evidence = {"rejection": {"code": [], "message": "bad code"}}

    def invoke(_observation, _handler, payload, _timeout):
        Path(payload["staged_snapshot_file"]).write_text(json.dumps(snapshot))
        return KernelInvocationResult(
            evidence, "/response.json", Diagnostics(exit_status=0)
        )

    services = OperationServices(
        probe_runtime=lambda _: runtime_observation(
            "aseprite_sprite_inspection", "aseprite_tile_inspection"
        ),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=LocalArtifactFiles(),
    )
    with pytest.raises(RuntimeIssue) as caught:
        get_tilemap(request, services)
    assert caught.value.kind == "response_malformed"
    assert destination.read_bytes() == b"previous artifact"
    assert source.read_bytes() == b"source"
    assert set(tmp_path.iterdir()) == {source, destination}
