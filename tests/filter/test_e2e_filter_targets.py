"""Filter target and palette basis behavior through persisted native Sprites."""

import json

import pytest

from tests.filter.support import apply, native_script, observe_images, pixels
from tests.support import inject_palette_change

pytestmark = pytest.mark.e2e


def test_selected_target_reports_cartesian_absences_without_creating_cels(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "target_scene.lua", source=source, mode="cartesian")
    before = observe_images(runtime, source)
    chosen = {
        "kind": "selected",
        "layers": [{"layer_path": [1]}, {"layer_path": [2]}],
        "frame_numbers": [1, 2, 3],
    }

    code, result = apply(source, target, pixels(cels_target=chosen))

    assert code == 0, result
    assert result["cels_target_kind"] == "selected"
    intersections = result["requested_intersections"]
    assert len(intersections) == 6
    assert len(result["existing_target_cels"]) == 3
    assert sum(item["image_number"] is None for item in intersections) == 3
    after = observe_images(runtime, target)
    assert {(cel["layer"], cel["frame"]) for cel in after["cels"]} == {
        ("Editable", 1),
        ("Editable", 3),
        ("Second", 2),
    }
    assert len(result["images"]) == 3
    assert all(item["changed"] for item in result["images"])
    assert before["cels"] != after["cels"]


def test_all_reports_noneditable_layers_and_changes_only_editable_cels(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "target_scene.lua", source=source, mode="exclusions")
    before = observe_images(runtime, source)

    code, result = apply(source, target, pixels(cels_target={"kind": "all"}))

    assert code == 0, result
    assert result["cels_target_kind"] == "all"
    assert len(result["existing_target_cels"]) == 1
    assert len(result["images"]) == 1
    assert len(result["excluded_layers"]) == 5
    assert {item["reason"] for item in result["excluded_layers"]} == {
        "cannot-edit-pixels"
    }
    assert any(len(item["layer_path"]) == 2 for item in result["excluded_layers"])
    after = observe_images(runtime, target)
    old = {cel["layer"]: cel["pixels"] for cel in before["cels"]}
    new = {cel["layer"]: cel["pixels"] for cel in after["cels"]}
    assert new["Editable"] != old["Editable"]
    assert all(new[name] == old[name] for name in old if name != "Editable")


def test_explicit_noneditable_layer_rejects_whole_operation_before_commit(
    tmp_path, runtime
):
    source, all_target = tmp_path / "source.aseprite", tmp_path / "all.aseprite"
    native_script(runtime, "target_scene.lua", source=source, mode="exclusions")
    source_bytes = source.read_bytes()
    code, all_result = apply(source, all_target, pixels(cels_target={"kind": "all"}))
    assert code == 0, all_result
    assert len(all_result["excluded_layers"]) == 5
    editable_path = all_result["existing_target_cels"][0]["layer_path"]

    for index, exclusion in enumerate(all_result["excluded_layers"]):
        target = tmp_path / f"existing-{index}.aseprite"
        target.write_bytes(b"previous target")
        chosen = {
            "kind": "selected",
            "layers": [
                {"layer_path": editable_path},
                {"layer_path": exclusion["layer_path"]},
            ],
            "frame_numbers": [1],
        }
        code, result = apply(source, target, pixels(cels_target=chosen), overwrite=True)
        assert code != 0 and result["code"] == "filter_invalid_target", (
            exclusion,
            result,
        )
        assert source.read_bytes() == source_bytes
        assert target.read_bytes() == b"previous target"


def test_linked_image_is_filtered_once_and_reports_link_outside_range(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "target_scene.lua", source=source, mode="linked")
    code, result = apply(source, target, pixels())

    assert code == 0, result
    assert len(result["existing_target_cels"]) == 1
    assert len(result["images"]) == 1
    assert result["processed_image_numbers"] == [1]
    assert {cel["frame_number"] for cel in result["affected_cels"]} == {1, 2}
    assert {cel["image_number"] for cel in result["affected_cels"]} == {1}
    after = observe_images(runtime, target)
    assert {cel["frame"] for cel in after["cels"]} == {1, 2}
    assert all((cel["pixels"][0] & 0xFF) == 150 for cel in after["cels"])


def _palette_source(runtime, source, mode):
    native_script(runtime, "target_palette_basis.lua", source=source, mode=mode)
    colors = [(0, 0, 0, 0), (20, 0, 0, 255)]
    if mode == "indexed":
        colors.append((120, 0, 0, 255))
    inject_palette_change(source, colors, frame_number=2)


def _palette_observation(runtime, source):
    response = source.with_suffix(".basis.json")
    native_script(
        runtime, "target_palette_observe.lua", source=source, response=response
    )
    return json.loads(response.read_text())


def test_indexed_pixel_basis_frame_can_differ_from_target_frame(tmp_path, runtime):
    source = tmp_path / "source.aseprite"
    _palette_source(runtime, source, "indexed")
    chosen = {"kind": "selected", "layers": [{"layer_path": [1]}], "frame_numbers": [1]}
    observations = {}
    for basis in (1, 2):
        target = tmp_path / f"basis-{basis}.aseprite"
        code, result = apply(
            source,
            target,
            pixels(
                "indexed",
                palette_frame_number=basis,
                cels_target=chosen,
                channels={"kind": "components", "names": ["red"]},
            ),
        )
        assert code == 0, result
        assert result["palette_basis"]["frame_number"] == basis
        assert {cel["frame_number"] for cel in result["existing_target_cels"]} == {1}
        observations[basis] = _palette_observation(runtime, target)
    assert observations[1]["target_pixel"] == 2
    assert observations[2]["target_pixel"] == 1
    assert observations[1]["anchor_pixel"] == observations[2]["anchor_pixel"] == 1
    assert observations[2]["palette_red"] == [80, 20]


def test_rgb_palette_basis_frame_can_differ_from_target_frame(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _palette_source(runtime, source, "rgb")
    chosen = {"kind": "selected", "layers": [{"layer_path": [1]}], "frame_numbers": [1]}
    application = {
        "kind": "rgb-palette-colors",
        "palette_frame_number": 2,
        "indexes": [1],
        "channels": {"kind": "components", "names": ["red"]},
        "cels_target": chosen,
    }

    code, result = apply(source, target, application)

    assert code == 0, result
    assert result["palette_basis"]["frame_number"] == 2
    assert {cel["frame_number"] for cel in result["existing_target_cels"]} == {1}
    assert result["palette_indexes"] == [1]
    after = _palette_observation(runtime, target)
    assert (after["target_pixel"] & 0xFF) == 30
    assert (after["anchor_pixel"] & 0xFF) == 20
    assert after["palette_red"] == [80, 30]


def test_canvas_selection_uses_cel_offset_and_changes_only_selected_pixel(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "target_scene.lua", source=source, mode="selection")
    selection = {"kind": "all", "rectangle": {"x": 2, "y": 0, "width": 1, "height": 1}}

    code, result = apply(source, target, pixels(selection=selection))

    assert code == 0, result
    assert result["selection"] == selection
    after = observe_images(runtime, target)["cels"][0]
    assert after["x"] == 1
    assert [(pixel & 0xFF) for pixel in after["pixels"]] == [100, 255]
