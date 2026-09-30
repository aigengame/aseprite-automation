"""Document and raster consumers agree on current paths and persisted identity."""

from pathlib import Path

import pytest

from tests.cel.test_e2e_cel import _fixture
from tests.paint.support import call_spa

pytestmark = pytest.mark.e2e

COLOR = {"kind": "rgba", "red": 17, "green": 34, "blue": 51, "alpha": 255}
AREA = {"x": 0, "y": 0, "width": 2, "height": 2}


def _success(*command: str, **request: object) -> dict:
    code, result = call_spa(*command, **request)
    assert code == 0, result
    return result


def _mutation(source: Path, target: Path) -> dict:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
    }


def _reordered_links(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source.aseprite"
    _fixture(source, "target_facts.lua")
    original = _success("layer", "list", sprite_file=str(source))
    leaf = original["layers"][1]["children"][0]["children"][0]
    assert leaf["path"] == [2, 1, 1]
    uuid = leaf["layer_uuid"]
    assert isinstance(uuid, str)

    linked = tmp_path / "linked.aseprite"
    duplicated = _success(
        "frame",
        "duplicate",
        **_mutation(source, linked),
        source_frame_number=1,
        cel_mode="link",
    )
    assert duplicated["cel_relationships"] == [
        {"layer_path": [2, 1, 1], "source_frame_number": 1, "kind": "link"}
    ]
    assert duplicated["persisted_reopen_verified"] is True
    moved = tmp_path / "moved.aseprite"
    _success(
        "layer",
        "move",
        **_mutation(linked, moved),
        target={"layer_path": [2]},
        stack_index=1,
    )
    addressed = _success(
        "layer", "get", sprite_file=str(moved), target={"layer_uuid": uuid}
    )
    assert addressed["layer"]["path"] == [1, 1, 1]
    assert addressed["layer"]["layer_uuid"] == uuid
    return moved, uuid


@pytest.mark.parametrize("paint", ["apply", "line"])
def test_reordered_nested_cels_keep_identity_paths_and_linked_raster_scope(
    tmp_path: Path,
    paint: str,
) -> None:
    source, uuid = _reordered_links(tmp_path)
    before = source.read_bytes()
    address = {"layer": {"layer_uuid": uuid}, "frame_number": 1}
    cel = _success("cel", "get", sprite_file=str(source), target=address)["cel"]
    assert cel["layer_path"] == [1, 1, 1]
    assert cel["linked_cels"] == [{"layer_path": [1, 1, 1], "frame_number": 2}]
    assert cel["position"] == {"x": 2, "y": 1}
    assert cel["image_bounds"] == {"x": 2, "y": 1, "width": 2, "height": 2}
    assert cel["opacity"] == 210 and cel["z_index"] == 2
    inspected = _success(
        "sprite", "get", sprite_file=str(source), inspection_scope=["cels"]
    )
    assert [item["layer_path"] for item in inspected["cels"]] == [[1, 1, 1], [1, 1, 1]]

    code, ambiguous = call_spa(
        "cel",
        "get",
        sprite_file=str(source),
        target={"layer": {"layer_name": "ink"}, "frame_number": 1},
    )
    assert code != 0 and ambiguous["code"] == "layer_ambiguous"
    output = tmp_path / "painted.aseprite"
    if paint == "apply":
        request = {
            "target": {"layer_path": [1, 1, 1], "frame_number": 1},
            "patch": {
                "coordinate_space": "image-pixel",
                "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                "runs": [{"x": 0, "y": 0, "length": 1, "color": COLOR}],
            },
        }
    else:
        request = {
            "target": address,
            "coordinate_space": "image-pixel",
            "from": {"x": 0, "y": 0},
            "to": {"x": 0, "y": 0},
            "brush": {"kind": "circle", "size": 1},
            "ink": "simple",
            "opacity": 255,
            "color": COLOR,
        }
    result = _success("paint", paint, **_mutation(source, output), **request)
    assert {
        (tuple(item["layer_path"]), item["frame_number"])
        for item in result["affected_cels"]
    } == {
        ((1, 1, 1), 1),
        ((1, 1, 1), 2),
    }
    assert result["linked_cels_preserved"] is True
    assert result["geometry_unchanged"] is True
    for number in (1, 2):
        reopened = _success(
            "cel",
            "get",
            sprite_file=str(output),
            target={"layer": {"layer_uuid": uuid}, "frame_number": number},
        )["cel"]
        for field in ("layer_path", "position", "image_bounds", "opacity", "z_index"):
            assert reopened[field] == cel[field]
        snapshot = _success(
            "image",
            "get",
            sprite_file=str(output),
            source={
                "kind": "individual",
                "target": {"layer": {"layer_uuid": uuid}, "frame_number": number},
                "rectangle": AREA,
            },
        )["snapshot"]
        assert snapshot["rows"][0][0]["color"] == COLOR
        assert snapshot["rows"][1] == [
            {
                "length": 2,
                "color": {
                    "kind": "rgba",
                    "red": 30,
                    "green": 40,
                    "blue": 50,
                    "alpha": 255,
                },
            }
        ]
    assert source.read_bytes() == before


def test_plan_reports_reordered_document_paths_and_preserves_uuid_after_reopen(
    tmp_path: Path,
) -> None:
    source, uuid = _reordered_links(tmp_path)
    target = tmp_path / "planned.aseprite"
    result = _success(
        "plan",
        "run",
        plan={
            **_mutation(source, target),
            "steps": [
                {
                    "operation": "frame duplicate",
                    "input": {"source_frame_number": 2, "cel_mode": "link"},
                },
                {
                    "operation": "cel set",
                    "input": {
                        "target": {"layer": {"layer_uuid": uuid}, "frame_number": 3},
                        "position": {"x": 1, "y": 0},
                    },
                },
                {
                    "operation": "sprite get",
                    "input": {"inspection_scope": ["layers", "cels"]},
                },
            ],
        },
    )
    duplicate = result["steps"][0]["result"]
    assert duplicate["cel_relationships"] == [
        {"layer_path": [1, 1, 1], "source_frame_number": 2, "kind": "link"}
    ]
    changed = result["steps"][1]["result"]
    assert changed["persisted_reopen_verified"] is False
    assert result["persisted_reopen_verified"] is True
    assert {tuple(item["layer_path"]) for item in changed["affected_cels"]} == {
        (1, 1, 1)
    }
    reopened = _success(
        "cel",
        "list",
        sprite_file=str(target),
        layer={"layer_uuid": uuid},
        from_frame=1,
        to_frame=3,
    )
    assert len(reopened["cels"]) == 3
    for cel in reopened["cels"]:
        assert cel["layer_path"] == [1, 1, 1]
        assert cel["position"] == {"x": 1, "y": 0}
        assert len(cel["linked_cels"]) == 2
