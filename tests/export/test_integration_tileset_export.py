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


@pytest.mark.parametrize(
    "damage",
    [
        "missing_metadata",
        "broken_json",
        "extra_field",
        "missing_key",
        "null_key",
        "index_as_key",
        "duplicate_tile",
        "wrong_flags",
        "incomplete_snapshot",
        "wrong_pixels",
        "wrong_profile",
        "unexpected_response",
        "wrong_map_frame",
    ],
)
def test_invalid_or_inconsistent_pair_is_never_published(
    tmp_path: Path, damage: str
) -> None:
    def corrupt(payload, evidence):
        metadata = Path(payload["staged_metadata_file"])
        value = json.loads(metadata.read_text())
        if damage == "missing_metadata":
            metadata.unlink()
            return
        if damage == "broken_json":
            metadata.write_text("{")
            return
        if damage == "extra_field":
            value["unexpected"] = True
        elif damage == "missing_key":
            del value["atlas"]["tiles"][1]["tile_key"]
        elif damage == "null_key":
            value["atlas"]["tiles"][1]["tile_key"] = None
        elif damage == "index_as_key":
            value["atlas"]["tiles"][1]["tile_key"] = "1"
        elif damage == "duplicate_tile":
            value["atlas"]["tiles"].append(value["atlas"]["tiles"][1])
        elif damage == "wrong_flags":
            value["snapshot"]["entries"][0]["placement"]["flip_x"] = False
        elif damage == "incomplete_snapshot":
            value["snapshot"]["complete"] = False
        elif damage == "wrong_pixels":
            Image.new("RGBA", (2, 1), (10, 20, 30, 128)).save(
                payload["staged_png_file"]
            )
        elif damage == "wrong_profile":
            from PIL import PngImagePlugin

            info = PngImagePlugin.PngInfo()
            info.add(b"sRGB", b"\x00")
            Image.frombytes("RGBA", (2, 1), bytes((0, 0, 0, 0, 10, 20, 30, 128))).save(
                payload["staged_png_file"], pnginfo=info
            )
        elif damage == "unexpected_response":
            evidence["unrequested_output"] = "other.png"
        elif damage == "wrong_map_frame":
            value["tilemap"]["frame_number"] = 2
            evidence["metadata"] = value
        metadata.write_text(json.dumps(value))

    with pytest.raises(RuntimeIssue) as caught:
        export_tileset(intent(tmp_path), services(corrupt=corrupt))
    assert caught.value.kind in {
        "artifact_file_failed",
        "artifact_verification_failed",
        "response_malformed",
    }
    assert not (tmp_path / "atlas.png").exists()
    assert not (tmp_path / "map.json").exists()
    assert not list(tmp_path.glob(".*.staged.*"))


def test_failure_before_first_path_change_is_not_partial_publication(
    tmp_path: Path,
) -> None:
    class CannotPublish(LocalArtifactFiles):
        def publish(self, staged, destination, **kwargs):
            raise RuntimeIssue(
                "artifact_file_failed",
                "Filesystem refused replacement",
                ArtifactFileEvidence(str(destination), "publication_failed"),
            )

    with pytest.raises(RuntimeIssue) as caught:
        export_tileset(intent(tmp_path), services(files=CannotPublish()))
    assert caught.value.kind == "artifact_file_failed"
    assert not (tmp_path / "atlas.png").exists()
    assert not (tmp_path / "map.json").exists()


def test_partial_publication_projects_registered_failure_details(
    tmp_path: Path,
) -> None:
    from spa.application.dispatch import dispatch
    from spa.application.failure_registry import FAILURE_CODES
    from spa.contracts.public import FailureEnvelope
    from spa.delivery.tileset import TILESET_EXPORT_OPERATIONS

    class SecondFails(LocalArtifactFiles):
        def publish(self, staged, destination, **kwargs):
            if destination.suffix == ".json":
                raise RuntimeIssue(
                    "artifact_file_failed",
                    "Injected publish failure",
                    ArtifactFileEvidence(str(destination), "publication_failed"),
                )
            return super().publish(staged, destination, **kwargs)

    outcome = dispatch(
        TILESET_EXPORT_OPERATIONS[0],
        intent(tmp_path).model_dump_json(),
        {},
        services(files=SecondFails()),
        FAILURE_CODES,
    )
    assert isinstance(outcome, FailureEnvelope)
    assert outcome.code == "partial_publication"
    value = outcome.model_dump(mode="json")
    assert value["details"]["destinations"][0]["state"] == "published"
    assert value["details"]["destinations"][1]["state"] == "not_published"
    assert "artifacts" not in value


def test_invalid_destination_is_rejected_before_native_execution(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    def must_not_run(*args):
        pytest.fail("Invalid destinations must fail before native execution")

    dependencies = replace(
        services(), probe_runtime=must_not_run, invoke_kernel=must_not_run
    )
    request = intent(tmp_path)
    request.metadata.path = str(tmp_path / "absent" / "map.json")
    with pytest.raises(RuntimeIssue) as caught:
        export_tileset(request, dependencies)
    assert caught.value.kind == "artifact_file_failed"
    assert not (tmp_path / "atlas.png").exists()


def test_destination_aliases_are_rejected_before_native_execution(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    image, metadata = tmp_path / "atlas.png", tmp_path / "map.json"
    metadata.write_bytes(b"existing")
    image.symlink_to(metadata)

    def must_not_run(*args):
        pytest.fail("Colliding destinations must fail before native execution")

    dependencies = replace(
        services(), probe_runtime=must_not_run, invoke_kernel=must_not_run
    )
    with pytest.raises(RuntimeIssue) as caught:
        export_tileset(intent(tmp_path, replace=True), dependencies)
    assert caught.value.kind == "artifact_file_failed"
    assert metadata.read_bytes() == b"existing"
