"""Tile Cell geometry is explicit and shared by standalone and Plan requests."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from spa.adapters.files import LocalTargetFiles
from spa.application.plan import PlanRunRequest, _requirements
from spa.application.surface import OPERATIONS, info_result
from spa.authoring.document.cel import CelAddRequest, add_cel
from spa.contracts.ports import OperationServices, RuntimeIssue
from spa.contracts.public import RuntimeRequest
from tests.support import operation_services, runtime_observation


def test_cel_add_and_plan_accept_explicit_tile_cell_dimensions() -> None:
    descriptor = next(item for item in OPERATIONS if item.name == "cel add")
    files = {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
    }
    cel_input = {
        "target": {"layer": {"layer_path": [2]}, "frame_number": 3},
        "tilemap_size": {"width": 2, "height": 3},
    }
    request = descriptor.request_type.model_validate(files | cel_input)
    plan = PlanRunRequest.model_validate(
        {"plan": files | {"steps": [{"operation": "cel add", "input": cel_input}]}}
    )
    assert request.model_dump()["tilemap_size"] == {"width": 2, "height": 3}
    assert plan.plan.steps[0].input.model_dump()["tilemap_size"] == {
        "width": 2,
        "height": 3,
    }


@pytest.mark.parametrize(
    "geometry",
    [
        {"tilemap_size": {"width": 0, "height": 1}},
        {"tilemap_size": {"width": True, "height": 1}},
        {"tilemap_size": {"width": 1.5, "height": 1}},
        {"tilemap_size": {"width": 1, "height": 65536}},
        {"tilemap_size": {"width": 1025, "height": 1024}},
        {
            "tilemap_size": {"width": 2, "height": 3},
            "image_size": {"width": 2, "height": 3},
        },
    ],
)
@pytest.mark.parametrize("plan", [False, True])
def test_invalid_or_mixed_geometry_is_rejected(geometry: dict, plan: bool) -> None:
    files = {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
    }
    cel_input = {
        "target": {"layer": {"layer_path": [2]}, "frame_number": 1},
        **geometry,
    }
    descriptor = next(item for item in OPERATIONS if item.name == "cel add")
    with pytest.raises(ValidationError):
        if plan:
            PlanRunRequest.model_validate(
                {
                    "plan": files
                    | {"steps": [{"operation": "cel add", "input": cel_input}]}
                }
            )
        else:
            descriptor.request_type.model_validate(files | cel_input)


@pytest.mark.parametrize("tilemap", [False, True])
def test_only_explicit_tilemap_plan_steps_require_creation_capability(
    tilemap: bool,
) -> None:
    request = PlanRunRequest.model_validate(
        {
            "plan": {
                "source_sprite_file": "source.aseprite",
                "target_sprite_file": "target.aseprite",
                "in_place": False,
                "overwrite": False,
                "steps": [
                    {
                        "operation": "cel add",
                        "input": {
                            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                            **(
                                {"tilemap_size": {"width": 2, "height": 3}}
                                if tilemap
                                else {}
                            ),
                        },
                    }
                ],
            }
        }
    )
    assert (
        "aseprite_tile_cel_creation"
        in _requirements(request.plan).required_capabilities
    ) == tilemap


@pytest.mark.parametrize("available", [False, True])
def test_discovery_preserves_ordinary_creation_and_reports_conditional_gap(
    available: bool,
) -> None:
    capabilities = ("aseprite_cel_lifecycle",) + (
        ("aseprite_tile_cel_creation",) if available else ()
    )
    result = info_result(
        RuntimeRequest(),
        operation_services(lambda _: runtime_observation(*capabilities)),
    )
    assert "spa cel add" in result.supported_capabilities
    assert any(
        gap.capability == "spa cel add: Tilemap Cel creation"
        for gap in result.capability_gaps
    ) == (not available)


def test_missing_creation_capability_refuses_before_staging(tmp_path: Path) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"Source")
    target.write_bytes(b"Target")

    def unexpected_invoke(*_):
        pytest.fail("incompatible runtime must not launch creation")

    services = OperationServices(
        probe_runtime=lambda _: runtime_observation("aseprite_cel_lifecycle"),
        invoke_kernel=unexpected_invoke,
        target_files=LocalTargetFiles(),
    )
    request = CelAddRequest.model_validate(
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "tilemap_size": {"width": 2, "height": 3},
        }
    )
    with pytest.raises(RuntimeIssue) as failure:
        add_cel(request, services)
    assert failure.value.kind == "runtime_incompatible"
    assert failure.value.evidence.missing_capabilities == (
        "aseprite_tile_cel_creation",
    )
    assert source.read_bytes() == b"Source" and target.read_bytes() == b"Target"
    assert set(tmp_path.iterdir()) == {source, target}
