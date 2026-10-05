"""Snapshot publication through real Operation and File Adapter interfaces."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.authoring.raster.image_snapshot import ImageGetRequest, get_image
from spa.authoring.tile.inspection import (
    TileGetRequest,
    TilemapGetRequest,
    get_tile,
    get_tilemap,
)
from spa.contracts.ports import (
    HandlerEvidence,
    KernelInvocationResult,
    OperationServices,
    RuntimeIssue,
)
from spa.contracts.public import Diagnostics
from tests.support import runtime_observation

DIAGNOSTICS = Diagnostics(exit_status=0, stderr="native observation")


@dataclass
class Caller:
    name: str
    source: Path
    original_source: Path
    destination: Path
    request: dict
    evidence: dict
    snapshot: dict

    def run(self, invoke, files):
        request_type, execute = {
            "image": (ImageGetRequest, get_image),
            "tile": (TileGetRequest, get_tile),
            "tilemap": (TilemapGetRequest, get_tilemap),
        }[self.name]
        return execute(
            request_type.model_validate(self.request),
            OperationServices(
                probe_runtime=lambda _: runtime_observation(),
                invoke_kernel=invoke,
                target_files=LocalTargetFiles(),
                artifact_files=files,
            ),
        )


@pytest.fixture(params=("image", "tile", "tilemap"))
def caller(request, tmp_path):
    original = tmp_path / "original.aseprite"
    original.write_bytes(b"source bytes")
    source = tmp_path / "source.aseprite"
    source.symlink_to(original)
    destination = tmp_path / "snapshot.json"
    destination.write_bytes(b"previous artifact")
    fields = {
        "sprite_file": str(source),
        "snapshot_destination": {"path": str(destination), "if_exists": "replace"},
    }
    rectangle = {"x": 0, "y": 0, "width": 1, "height": 1}
    color = {"kind": "rgba", "red": 1, "green": 2, "blue": 3, "alpha": 0}
    snapshot = {
        "coordinate_space": "image-pixel",
        "color_mode": "rgb",
        "rectangle": rectangle,
        "rows": [[{"length": 1, "color": color}]],
    }
    if request.param == "image":
        fields["source"] = {
            "kind": "composite",
            "frame_number": 1,
            "output_color_mode": "preserve",
            "rectangle": rectangle,
            "layer_composition": {"mode": "visible"},
        }
        evidence = {
            "source": {
                **fields["source"],
                "coordinate_space": "canvas-pixel",
                "color_mode": "rgb",
                "mask_color": color,
                "resolved_layer_paths": [[1]],
                "compose_groups": True,
                "reference_layers_rendered": False,
            },
            "snapshot": None,
            "width": 1,
            "height": 1,
            "color_mode": "rgb",
            "mask_color": color,
            "effective_palettes": [],
        }
    else:
        grid = {"origin": {"x": 0, "y": 0}, "tile_size": {"width": 1, "height": 1}}
        layer = {"layer_path": [1], "layer_uuid": None, "name": "map"}
        evidence = {
            "sprite_file": str(source),
            "tileset": {
                "tileset_index": 1,
                "name": "terrain",
                "base_index": 1,
                "tile_count": 2,
                "grid": grid,
                "layers": [layer],
            },
            "snapshot": None,
            "output_form": "artifact",
        }
        if request.param == "tile":
            fields.update(target={"tileset_index": 1}, tile={"tile_index": 1})
            evidence["tile"] = {
                "tile_index": 1,
                "tile_key": "grass",
                "display_index": 2,
                "image_size": {"width": 1, "height": 1},
                "color_mode": "rgb",
                "data": "",
                "color": {"red": 1, "green": 2, "blue": 3, "alpha": 0},
                "properties": [
                    {"namespace": name, "value": {"kind": "table", "entries": []}}
                    for name in ("", "aigengame.spa")
                ],
            }
        else:
            fields.update(
                target={"layer": {"layer_path": [1]}, "frame_number": 1},
                rectangle=rectangle,
            )
            evidence["tilemap"] = {
                "layer": layer,
                "tileset_index": 1,
                "frame_number": 1,
                "exists": True,
                "position": {"x": 0, "y": 0},
                "cell_size": {"width": 1, "height": 1},
                "effective_grid": grid,
                "canvas_coverage": rectangle,
            }
            snapshot = {"rectangle": rectangle, "entries": []}
    return Caller(
        request.param, source, original, destination, fields, evidence, snapshot
    )


def test_verified_snapshot_is_published_once_with_actual_artifact_facts(caller):
    invocations = []
    raw = json.dumps(caller.snapshot).encode()

    def invoke(_observation, _handler, payload, _timeout):
        staged = Path(payload["staged_snapshot_file"])
        invocations.append(staged)
        staged.write_bytes(raw)
        return KernelInvocationResult(caller.evidence, "/response.json", DIAGNOSTICS)

    result = caller.run(invoke, LocalArtifactFiles())
    assert result.output_form == "artifact" and result.snapshot is None
    assert result.artifact.path == str(caller.destination)
    assert result.artifact.byte_size == len(raw)
    assert result.artifact.sha256 == hashlib.sha256(raw).hexdigest()
    assert result.artifact.role == (
        "tile-region-snapshot" if caller.name == "tilemap" else "pixel-region-snapshot"
    )
    assert caller.destination.read_bytes() == raw
    assert caller.original_source.read_bytes() == b"source bytes"
    assert len(invocations) == 1 and not invocations[0].exists()
    assert set(caller.destination.parent.iterdir()) == {
        caller.source,
        caller.original_source,
        caller.destination,
    }


@pytest.mark.parametrize(
    ("fault", "kind", "reason"),
    [
        ("native_failed", "handler_rejected", "native refused"),
        ("missing_snapshot", "artifact_file_failed", "staged_file_missing"),
        ("empty_snapshot", "artifact_file_failed", "staged_file_empty"),
        ("malformed_snapshot", "response_malformed", None),
        ("malformed_evidence", "response_malformed", None),
        ("snapshot_mismatch", "response_malformed", None),
        ("scope_mismatch", "response_malformed", None),
        ("inline_and_artifact", "response_malformed", None),
        ("source_alias_changed", "artifact_file_failed", "source_destination_alias"),
        ("snapshot_changed", "artifact_file_failed", "staged_file_changed"),
        ("publication_failed", "artifact_file_failed", "publication_failed"),
    ],
)
def test_failed_snapshot_publication_preserves_files_and_cleans_staging(
    caller, monkeypatch, fault, kind, reason
):
    staged_paths = []

    def invoke(_observation, _handler, payload, _timeout):
        staged = Path(payload["staged_snapshot_file"])
        staged_paths.append(staged)
        if fault == "snapshot_mismatch":
            caller.snapshot["rectangle"] = {"x": 0, "y": 0, "width": 2, "height": 1}
            if "rows" in caller.snapshot:
                caller.snapshot["rows"][0][0]["length"] = 2
        staged.write_text(json.dumps(caller.snapshot))
        if fault == "native_failed":
            raise RuntimeIssue(
                "handler_rejected",
                "Native refused",
                HandlerEvidence("/response.json", "native refused"),
                DIAGNOSTICS,
            )
        if fault == "missing_snapshot":
            staged.unlink()
        elif fault == "empty_snapshot":
            staged.write_bytes(b"")
        elif fault == "malformed_snapshot":
            staged.write_bytes(b"not JSON")
        elif fault == "malformed_evidence":
            caller.evidence.clear()
        elif fault == "scope_mismatch":
            if caller.name == "image":
                caller.evidence["source"]["frame_number"] = 2
            else:
                caller.evidence["sprite_file"] = "other.aseprite"
        elif fault == "inline_and_artifact":
            caller.evidence["snapshot"] = caller.snapshot
        elif fault == "source_alias_changed":
            caller.source.unlink()
            caller.source.symlink_to(caller.destination)
        return KernelInvocationResult(caller.evidence, "/response.json", DIAGNOSTICS)

    class ChangingFiles(LocalArtifactFiles):
        def publish(self, staged, destination, *, if_exists, sha256):
            if fault == "snapshot_changed":
                # The owner has completed domain validation before publication.
                staged.write_bytes(staged.read_bytes() + b" ")
            return super().publish(
                staged, destination, if_exists=if_exists, sha256=sha256
            )

    if fault == "publication_failed":

        def refuse_replace(*_args):
            raise PermissionError("publication denied")

        monkeypatch.setattr("spa.adapters.files.os.replace", refuse_replace)

    with pytest.raises(RuntimeIssue) as caught:
        caller.run(invoke, ChangingFiles())
    assert caught.value.kind == kind
    if reason is not None:
        assert caught.value.evidence.reason == reason
    if kind == "response_malformed":
        assert caught.value.evidence.response_path == "/response.json"
        assert caught.value.diagnostics == DIAGNOSTICS
    assert caller.destination.read_bytes() == b"previous artifact"
    assert caller.original_source.read_bytes() == b"source bytes"
    assert len(staged_paths) == 1 and not staged_paths[0].exists()


def test_missing_artifact_and_invalid_native_evidence_keep_failure_precedence(caller):
    def invoke(_observation, _handler, _payload, _timeout):
        return KernelInvocationResult({}, "/response.json", DIAGNOSTICS)

    with pytest.raises(RuntimeIssue) as caught:
        caller.run(invoke, LocalArtifactFiles())
    # Image observes staged bytes before parsing native facts; Tile does the reverse.
    assert caught.value.kind == (
        "artifact_file_failed" if caller.name == "image" else "response_malformed"
    )
    assert caller.destination.read_bytes() == b"previous artifact"
    assert caller.original_source.read_bytes() == b"source bytes"
    assert not list(caller.destination.parent.glob(".*.staged.json"))


@pytest.mark.parametrize("fault", ("alias", "existing_destination"))
def test_destination_refusal_precedes_native_execution(caller, fault):
    if fault == "alias":
        caller.source.unlink()
        caller.source.symlink_to(caller.destination)
    else:
        caller.request["snapshot_destination"]["if_exists"] = "fail"

    def invoke(*_args):
        pytest.fail("Refused destination must not invoke Aseprite")

    with pytest.raises(RuntimeIssue) as caught:
        caller.run(invoke, LocalArtifactFiles())
    assert caught.value.kind == "artifact_file_failed"
    assert caught.value.evidence.reason == (
        "source_destination_alias" if fault == "alias" else "destination_exists"
    )
    assert caller.destination.read_bytes() == b"previous artifact"
    assert caller.original_source.read_bytes() == b"source bytes"
    assert not list(caller.destination.parent.glob(".*.staged.json"))


def test_destination_appearing_during_native_read_is_not_replaced(caller):
    caller.destination.unlink()
    caller.request["snapshot_destination"]["if_exists"] = "fail"

    def invoke(_observation, _handler, payload, _timeout):
        Path(payload["staged_snapshot_file"]).write_text(json.dumps(caller.snapshot))
        caller.destination.write_bytes(b"concurrent destination")
        return KernelInvocationResult(caller.evidence, "/response.json", DIAGNOSTICS)

    with pytest.raises(RuntimeIssue) as caught:
        caller.run(invoke, LocalArtifactFiles())
    assert caught.value.kind == "artifact_file_failed"
    assert caught.value.evidence.reason == "destination_exists"
    assert caller.destination.read_bytes() == b"concurrent destination"
    assert caller.original_source.read_bytes() == b"source bytes"
    assert not list(caller.destination.parent.glob(".*.staged.json"))


def test_inline_snapshot_needs_no_artifact_files(caller):
    caller.request.pop("snapshot_destination")
    caller.evidence["snapshot"] = caller.snapshot
    if caller.name != "image":
        caller.evidence["output_form"] = "inline"

    def invoke(_observation, _handler, payload, _timeout):
        assert "staged_snapshot_file" not in payload
        return KernelInvocationResult(caller.evidence, "/response.json", DIAGNOSTICS)

    result = caller.run(invoke, None)
    assert result.output_form == "inline" and result.artifact is None
    assert result.snapshot is not None
    assert result.snapshot.rectangle.width == 1
    assert caller.destination.read_bytes() == b"previous artifact"
    assert caller.original_source.read_bytes() == b"source bytes"


def test_tilemap_summary_needs_no_artifact_files(tmp_path):
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    grid = {"origin": {"x": 0, "y": 0}, "tile_size": {"width": 1, "height": 1}}
    layer = {"layer_path": [1], "layer_uuid": None, "name": "map"}
    evidence = {
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
            "exists": False,
            "position": None,
            "cell_size": None,
            "effective_grid": None,
            "canvas_coverage": None,
        },
        "snapshot": None,
        "output_form": "summary",
    }

    def invoke(_observation, _handler, payload, _timeout):
        assert "staged_snapshot_file" not in payload
        return KernelInvocationResult(evidence, "/response.json", DIAGNOSTICS)

    result = get_tilemap(
        TilemapGetRequest.model_validate(
            {
                "sprite_file": str(source),
                "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            }
        ),
        OperationServices(lambda _: runtime_observation(), invoke, LocalTargetFiles()),
    )
    assert result.output_form == "summary"
    assert result.artifact is None and result.snapshot is None
    assert set(tmp_path.iterdir()) == {source}
