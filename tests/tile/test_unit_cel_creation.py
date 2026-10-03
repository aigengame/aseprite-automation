"""Tile Cell geometry is explicit and shared by standalone and Plan requests."""

import pytest
from pydantic import ValidationError

from spa.application.plan import PlanRunRequest
from spa.application.surface import OPERATIONS


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
