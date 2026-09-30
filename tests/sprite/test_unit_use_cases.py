"""Sprite use-case postconditions at the Domain Module boundary."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from spa.authoring.document.sprite import (
    SpriteCreateRequest,
    SpriteCropRequest,
    SpriteGetRequest,
    create_sprite,
    crop_sprite,
    get_sprite,
)
from spa.contracts.ports import (
    KernelInvocationResult,
    OperationServices,
    RuntimeIssue,
    RuntimeObservation,
    TargetCommitObservation,
)
from spa.contracts.public import Diagnostics


def _observation() -> RuntimeObservation:
    return RuntimeObservation(
        selection_source="explicit",
        requested_path="/aseprite",
        discovered_path="/aseprite",
        canonical_path="/aseprite",
        resource_path="/data/gui.xml",
        aseprite_version="test",
        api_version=41,
        lua_version="Lua 5.4",
        verified_prerequisites=(
            "aseprite_scripting",
            "lua_file_io",
            "aseprite_json",
        ),
        verified_capabilities=(
            "aseprite_sprite_create",
            "aseprite_sprite_inspection",
        ),
    )


def _inspection(**overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "metadata": {
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "frame_count": 1,
            "tag_count": 0,
            "palette_count": 1,
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
        "palettes": [{"frame_number": 1, "entries": []}],
        "layers": [
            {
                "path": [1],
                "name": "Layer 1",
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
                "bounds": {"x": 0, "y": 0, "width": 3, "height": 2},
                "opacity": 255,
                "z_index": 0,
            }
        ],
        "slices": [],
        "tilesets": [],
    }
    result.update(overrides)
    return result


@dataclass
class _TargetFiles:
    commits: int = 0
    overwrite: bool | None = None

    def staged_path(self, target: Path) -> Path:
        return target.with_suffix(".staged.aseprite")

    def commit(
        self, staged: Path, target: Path, *, overwrite: bool
    ) -> TargetCommitObservation:
        self.commits += 1
        self.overwrite = overwrite
        return TargetCommitObservation(str(target), 1, "0" * 64)

    def discard(self, staged: Path) -> None:
        return None

    def same_publication_entry(self, source: Path, target: Path) -> bool:
        return False

    def same_publication_target(self, source: Path, target: Path) -> bool:
        return False


def _services(
    payload: dict[str, Any], files: _TargetFiles | None = None
) -> OperationServices:
    target_files = files or _TargetFiles()

    def invoke(*_args: object) -> KernelInvocationResult:
        return KernelInvocationResult(
            payload={
                "sprite": payload,
                "persisted_initial_layer": {"kind": "transparent"},
            },
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    return OperationServices(
        probe_runtime=lambda _request: _observation(),
        invoke_kernel=invoke,
        target_files=target_files,
    )


def test_create_refuses_mismatched_persisted_facts_before_target_commit() -> None:
    files = _TargetFiles()
    inspection = _inspection()
    inspection["metadata"] = inspection["metadata"] | {"width": 4}
    request = SpriteCreateRequest(
        target_sprite_file="created.aseprite",
        width=3,
        height=2,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=False,
    )

    with pytest.raises(RuntimeIssue, match="postconditions") as failure:
        create_sprite(request, _services(inspection, files))

    assert failure.value.kind == "postcondition_failed"
    assert files.commits == 0


def test_crop_requires_kernel_clipping_evidence_before_target_commit() -> None:
    files = _TargetFiles()
    before = _inspection()
    after = _inspection()
    after["metadata"]["width"] = 2
    after["cels"][0]["bounds"]["width"] = 2

    def invoke(*_args: object) -> KernelInvocationResult:
        return KernelInvocationResult(
            payload={
                "before_sprite": before,
                "sprite": after,
                "persisted_reopen_verified": True,
            },
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    services = OperationServices(
        probe_runtime=lambda _request: _observation(),
        invoke_kernel=invoke,
        target_files=files,
    )
    request = SpriteCropRequest(
        source_sprite_file="source.aseprite",
        target_sprite_file="target.aseprite",
        in_place=False,
        overwrite=False,
        coordinate_space="canvas-pixel",
        rectangle={"x": 0, "y": 0, "width": 2, "height": 2},
    )

    with pytest.raises(RuntimeIssue) as failure:
        crop_sprite(request, services)

    assert failure.value.kind == "response_malformed"
    assert files.commits == 0


def test_create_refuses_incomplete_section_before_target_commit() -> None:
    files = _TargetFiles()
    request = SpriteCreateRequest(
        target_sprite_file="created.aseprite",
        width=3,
        height=2,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=False,
    )

    with pytest.raises(RuntimeIssue, match="metadata declares 1"):
        create_sprite(request, _services(_inspection(frames=[]), files))

    assert files.commits == 0


@pytest.mark.parametrize("overwrite", [False, True])
def test_create_forwards_explicit_overwrite_to_target_commit(overwrite: bool) -> None:
    files = _TargetFiles()
    request = SpriteCreateRequest(
        target_sprite_file="created.aseprite",
        width=3,
        height=2,
        color_mode="rgb",
        initial_layer={"kind": "transparent"},
        overwrite=overwrite,
    )

    result = create_sprite(request, _services(_inspection(), files))

    assert result.persisted_reopen_verified is True
    assert files.commits == 1
    assert files.overwrite is overwrite


@pytest.mark.parametrize(
    "inspection",
    [
        _inspection(frames=None),
        _inspection(frames=[]),
        _inspection(tags=[]),
    ],
    ids=[
        "requested-section-null",
        "requested-section-count-mismatch",
        "unrequested-section-populated",
    ],
)
def test_get_refuses_false_scope_completeness(inspection: dict[str, Any]) -> None:
    request = SpriteGetRequest(
        sprite_file="created.aseprite", inspection_scope=["frames"]
    )

    with pytest.raises(RuntimeIssue) as failure:
        get_sprite(request, _services(inspection))

    assert failure.value.kind == "postcondition_failed"


def test_get_refuses_incomplete_nonempty_slices() -> None:
    request = SpriteGetRequest(
        sprite_file="created.aseprite", inspection_scope=["slices"]
    )
    inspection = _inspection(
        frames=None,
        tags=None,
        palettes=None,
        layers=None,
        cels=None,
        slices=None,
        tilesets=None,
    )
    inspection["metadata"] = inspection["metadata"] | {"slice_count": 1}

    with pytest.raises(RuntimeIssue) as unsupported:
        get_sprite(request, _services(inspection))
    assert unsupported.value.kind == "postcondition_failed"

    inspection["metadata"] = inspection["metadata"] | {"slice_count": 0}
    with pytest.raises(RuntimeIssue) as failure:
        get_sprite(request, _services(inspection))
    assert failure.value.kind == "postcondition_failed"
