"""The finite recipe edits motion while frozen art and native timing stay fixed."""

from copy import deepcopy

from examples.wizard_cast_v2 import art


def test_bob_revision_moves_attached_gem_without_redrawing_pose_or_changing_time() -> (
    None
):
    recipe = art.load_recipe()
    changed = deepcopy(recipe)
    changed["motion"]["idle_bob_pixels"] += 1
    original = art.sample_frame(recipe, 2)
    revised = art.sample_frame(changed, 2)
    for name in ("wizard", "gem"):
        assert original[name].pixels == revised[name].pixels
        assert revised[name].position == (
            original[name].position[0],
            original[name].position[1] - 1,
        )
    assert original["background"] == revised["background"]
    assert art.phases(changed) == art.phases(recipe)
    assert art.total_frames(changed) == 32


def test_review_scene_shake_is_removed_from_component_exports() -> None:
    frame = art.sample_frame(art.load_recipe(), 14)
    for name, component in frame.items():
        if name == "projectile":
            assert component.local_position == (0, 0)
        else:
            assert component.position == (
                component.local_position[0] + 2,
                component.local_position[1] - 1,
            )


def test_local_components_fit_declared_crops_at_every_frame() -> None:
    recipe = art.load_recipe()
    for index in range(32):
        frame = art.sample_frame(recipe, index)
        for name, definition in recipe["export"]["components"].items():
            if name == "background":
                continue  # Its declared overscan is deliberately outside the crop.
            crop = definition["crop"]
            for layer in definition["layers"]:
                component = frame[layer]
                for x, y in component.pixels:
                    assert (
                        crop["x"]
                        <= x + component.local_position[0]
                        < crop["x"] + crop["width"]
                    )
                    assert (
                        crop["y"]
                        <= y + component.local_position[1]
                        < crop["y"] + crop["height"]
                    )
