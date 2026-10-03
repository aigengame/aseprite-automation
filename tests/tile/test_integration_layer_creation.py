"""Explicit Tilemap intent and evidence gate Target publication."""

import json
import os
import shlex
from pathlib import Path

import pytest
from jsonschema import validate

from spa.adapters.files import LocalTargetFiles
from spa.application.surface import info_result
from spa.authoring.document.layer import LAYER_REQUIREMENTS, LayerAddRequest, add_layer
from spa.contracts.ports import KernelInvocationResult, OperationServices, RuntimeIssue
from spa.contracts.public import Diagnostics, RuntimeRequest
from tests.support import fake_aseprite, operation_services, runtime_observation, spa


def create_intent() -> dict:
    return {
        "create": {
            "name": "terrain",
            "grid": {
                "origin": {"x": 0, "y": 0},
                "tile_size": {"width": 2, "height": 3},
            },
            "base_index": -32768,
        }
    }


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable fixture")
@pytest.mark.parametrize(
    "defect",
    [
        "x",
        "y",
        "base-low",
        "base-high",
        "missing",
        "both",
        "share-missing",
        "share-both",
        "ordinary",
        "nul",
    ],
)
def test_invalid_intent_is_rejected_before_runtime(tmp_path: Path, defect: str) -> None:
    marker = tmp_path / "invoked"
    binary = fake_aseprite(tmp_path, f"touch {shlex.quote(str(marker))}\nexit 1")
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    intent = create_intent()
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
        "kind": "tilemap",
        "name": "map",
        "tileset": intent,
        "aseprite": str(binary),
    }
    if defect in ("x", "y"):
        intent["create"]["grid"]["origin"][defect] = 1
    elif defect.startswith("base-"):
        intent["create"]["base_index"] = -32769 if defect == "base-low" else 32768
    elif defect == "missing":
        del request["tileset"]
    elif defect == "both":
        intent["share"] = {"tileset_index": 1}
    elif defect == "share-missing":
        request["tileset"] = {"share": {}}
    elif defect == "share-both":
        request["tileset"] = {"share": {"tileset_index": 1, "tileset_name": "terrain"}}
    elif defect == "ordinary":
        request["kind"] = "transparent"
    else:
        intent["create"]["name"] = "terrain\x00suffix"
    result = spa("layer", "add", "--input-json", json.dumps(request))
    failure = json.loads(result.stdout)
    assert result.returncode == 2, failure
    assert failure["code"] == "invalid_request"
    assert not marker.exists()
    assert source.read_bytes() == b"source"
    assert target.read_bytes() == b"target"


def test_schema_describes_persistence_bounds() -> None:
    schema = json.loads(spa("layer", "add", "--schema").stdout)["request_schema"]
    for name in ("x", "y"):
        origin = schema["$defs"]["TilesetOrigin"]["properties"][name]
        assert origin["minimum"] == origin["maximum"] == 0
    base = schema["$defs"]["TilesetCreate"]["properties"]["base_index"]
    assert (base["minimum"], base["maximum"]) == (-32768, 32767)


def _receipt() -> dict:
    layer = {
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
    return {
        "added_path": [1],
        "before_layer_count": 0,
        "before_use_layer_uuids": False,
        "sprite": {
            "metadata": {
                "width": 4,
                "height": 4,
                "color_mode": "rgb",
                "frame_count": 1,
                "tag_count": 0,
                "palette_count": 0,
                "layer_count": 1,
                "cel_count": 0,
                "slice_count": 0,
                "tileset_count": 1,
                "transparent_color_index": 0,
                "grid_bounds": {"x": 0, "y": 0, "width": 1, "height": 1},
                "pixel_ratio": {"width": 1, "height": 1},
                "use_layer_uuids": False,
            },
            "layers": [layer],
            "frames": None,
            "tags": None,
            "palettes": None,
            "cels": None,
            "slices": None,
            "tilesets": None,
        },
        "tilemap": {
            "intent": "create",
            "before_tileset_count": 0,
            "tileset_count": 1,
            "initial_cel_count": 0,
            "temporary_tilesets_removed": 0,
            "shared_tileset_before": None,
            "tileset": {
                **create_intent()["create"],
                "tileset_index": 1,
                "tile_count": 1,
                "layers": [{"layer_path": [1], "name": "map", "layer_uuid": None}],
            },
        },
    }


@pytest.mark.parametrize(
    "defect", [None, "count", "binding", "grid", "cel", "removed", "intent", "missing"]
)
def test_receipt_must_match_intent_before_target_commit(
    tmp_path: Path, defect: str | None
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    request = LayerAddRequest.model_validate(
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            "kind": "tilemap",
            "name": "map",
            "tileset": create_intent(),
        }
    )
    receipt = _receipt()
    evidence = receipt["tilemap"]
    if defect == "count":
        evidence["tileset_count"] = 2
    elif defect == "binding":
        evidence["tileset"]["layers"][0]["layer_path"] = [2]
    elif defect == "grid":
        evidence["tileset"]["grid"]["origin"]["x"] = 1
    elif defect == "cel":
        evidence["initial_cel_count"] = 1
    elif defect == "removed":
        evidence["temporary_tilesets_removed"] = 1
    elif defect == "intent":
        evidence["intent"] = "share"
    elif defect == "missing":
        del receipt["tilemap"]

    def invoke(_runtime, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"verified candidate")
        return KernelInvocationResult(
            receipt, "/response.json", Diagnostics(exit_status=0)
        )

    services = OperationServices(
        probe_runtime=lambda _: runtime_observation("aseprite_tilemap_layer_creation"),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
    )
    if defect is None:
        result = add_layer(request, services)
        schema = json.loads(spa("layer", "add", "--schema").stdout)
        validate(result.model_dump(mode="json"), schema["result_schema"])
        assert target.read_bytes() == b"verified candidate"
    else:
        with pytest.raises(RuntimeIssue) as failure:
            add_layer(request, services)
        assert failure.value.kind == "response_malformed"
        assert target.read_bytes() == b"target"
    assert source.read_bytes() == b"source"
    assert set(tmp_path.iterdir()) == {source, target}


def test_missing_creation_capability_keeps_ordinary_layer_available(
    tmp_path: Path,
) -> None:
    observation = runtime_observation(*LAYER_REQUIREMENTS.required_capabilities)
    info = info_result(RuntimeRequest(), operation_services(lambda _: observation))
    assert "spa layer add" in info.supported_capabilities
    assert "spa layer add: tilemap" in [gap.capability for gap in info.capability_gaps]
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"source")
    request = LayerAddRequest.model_validate(
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "kind": "tilemap",
            "name": "map",
            "tileset": create_intent(),
        }
    )

    def unexpected_invocation(*_args):
        pytest.fail("Tilemap handler must not run without native capability")

    with pytest.raises(RuntimeIssue) as failure:
        add_layer(
            request,
            OperationServices(
                probe_runtime=lambda _: observation,
                invoke_kernel=unexpected_invocation,
                target_files=LocalTargetFiles(),
            ),
        )
    assert failure.value.kind == "runtime_incompatible"
    assert set(tmp_path.iterdir()) == {source}
