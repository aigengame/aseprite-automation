"""Complete-pair validation and publication failures at the Kernel/file boundaries."""

import json
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png_input import decode_png_artifact
from spa.contracts.digest import fnv1a64
from spa.contracts.ports import (
    ArtifactFileEvidence,
    KernelInvocationResult,
    OperationServices,
    PartialPublicationEvidence,
    RuntimeIssue,
)
from spa.contracts.public import Diagnostics
from spa.delivery.tileset import export_tileset
from spa.delivery.tileset_contracts import ExportTilesetRequest
from tests.support import runtime_observation


def intent(root: Path, *, replace=False) -> ExportTilesetRequest:
    return ExportTilesetRequest.model_validate(
        {
            "source_sprite_file": str(root / "source.aseprite"),
            "tileset": {"tileset_index": 1},
            "target": {"layer": {"layer_path": [2]}, "frame_number": 1},
            "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
            "columns": 2,
            "image": {
                "path": str(root / "atlas.png"),
                "if_exists": "replace" if replace else "fail",
            },
            "metadata": {
                "path": str(root / "map.json"),
                "if_exists": "replace" if replace else "fail",
            },
        }
    )


def native_output(payload: dict) -> dict:
    layer = {"layer_path": [2], "layer_uuid": None, "name": "map"}
    size = {"width": 1, "height": 1}
    return {
        "schema_version": 1,
        "source_sprite_file": payload["source_sprite_file"],
        "tileset": {
            "tileset_index": 1,
            "name": "terrain",
            "base_index": 5,
            "tile_count": 2,
            "grid": {"origin": {"x": 0, "y": 0}, "tile_size": size},
            "layers": [layer],
        },
        "tilemap": {
            "layer": layer,
            "tileset_index": 1,
            "frame_number": 1,
            "exists": True,
            "position": {"x": -2, "y": 4},
            "cell_size": size,
            "effective_grid": {"origin": {"x": -2, "y": 4}, "tile_size": size},
            "canvas_coverage": {"x": -2, "y": 4, **size},
        },
        "snapshot": {
            "coordinate_space": "tile-cell",
            "rectangle": {"x": 0, "y": 0, **size},
            "complete": True,
            "default": {"kind": "empty"},
            "entries": [
                {
                    "tile_x": 0,
                    "tile_y": 0,
                    "placement": {
                        "kind": "tile",
                        "tile_index": 1,
                        "tile_key": "grass",
                        "flip_x": True,
                        "flip_y": False,
                        "flip_diagonal": False,
                    },
                }
            ],
        },
        "atlas": {
            "path": payload["image_path"],
            "width": 2,
            "height": 1,
            "columns": 2,
            "color_mode": "rgb",
            "profile": {"kind": "none", "icc_identity": None},
            "png": {"bit_depth": 8, "color_type": 6},
            "palette": None,
            "tiles": [
                {
                    "kind": "empty",
                    "tile_index": 0,
                    "rectangle": {"x": 0, "y": 0, **size},
                },
                {
                    "kind": "tile",
                    "tile_index": 1,
                    "tile_key": "grass",
                    "rectangle": {"x": 1, "y": 0, **size},
                },
            ],
        },
    }


def services(*, files=None, corrupt=None) -> OperationServices:
    def invoke(_runtime, _handler, payload, _timeout):
        value = native_output(payload)
        Image.frombytes("RGBA", (2, 1), bytes((0, 0, 0, 0, 10, 20, 30, 128))).save(
            payload["staged_png_file"]
        )
        Path(payload["staged_metadata_file"]).write_text(json.dumps(value))
        evidence = {
            "metadata": value,
            "tile_digests": [fnv1a64(bytes(4)), fnv1a64(bytes((10, 20, 30, 128)))],
        }
        if corrupt:
            corrupt(payload, evidence)
        return KernelInvocationResult(
            evidence, "/response.json", Diagnostics(exit_status=0)
        )

    return OperationServices(
        probe_runtime=lambda _: runtime_observation(
            "aseprite_tile_inspection", "aseprite_export_image"
        ),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
        artifact_files=files or LocalArtifactFiles(),
        decode_png_artifact=decode_png_artifact,
    )


def test_second_publication_failure_reports_pair_without_rollback(
    tmp_path: Path,
) -> None:
    class FailingMetadata(LocalArtifactFiles):
        def publish(self, staged, destination, **kwargs):
            if destination.suffix == ".json":
                raise RuntimeIssue(
                    "artifact_file_failed",
                    "Injected before metadata publication",
                    ArtifactFileEvidence(str(destination), "destination_exists"),
                )
            return super().publish(staged, destination, **kwargs)

    image, metadata = tmp_path / "atlas.png", tmp_path / "map.json"
    image.write_bytes(b"old image")
    metadata.write_bytes(b"old metadata")
    with pytest.raises(RuntimeIssue) as caught:
        export_tileset(
            intent(tmp_path, replace=True), services(files=FailingMetadata())
        )
    assert caught.value.kind == "partial_publication"
    evidence = caught.value.evidence
    assert isinstance(evidence, PartialPublicationEvidence)
    assert [
        (item.role, item.state, item.existed_before, item.replaced_existing)
        for item in evidence.destinations
    ] == [
        ("tileset-image", "published", True, True),
        ("map-data", "not_published", True, None),
    ]
    assert image.read_bytes().startswith(b"\x89PNG")
    assert metadata.read_bytes() == b"old metadata"
    assert list(
        tmp_path.glob(".*.staged.json")
    )  # Preserve the unpublished staged file.
