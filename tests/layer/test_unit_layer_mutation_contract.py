"""Descriptor and native vocabulary contracts for Layer mutations."""

import re
from importlib.resources import files
from typing import get_args

from spa.layer import LAYER_OPERATIONS, BlendModeName


def test_layer_mutations_require_hierarchy_capability() -> None:
    for descriptor in LAYER_OPERATIONS:
        if descriptor.name not in {
            "layer set",
            "layer move",
            "layer remove",
            "layer merge",
        }:
            continue
        assert "aseprite_layer_hierarchy" in (
            descriptor.runtime_requirements.required_capabilities
        )


def test_invalid_position_applies_only_to_move() -> None:
    for descriptor in LAYER_OPERATIONS:
        if descriptor.name not in {
            "layer set",
            "layer move",
            "layer remove",
            "layer merge",
        }:
            continue
        assert ("layer_invalid_position" in descriptor.failure_codes) is (
            descriptor.name == "layer move"
        )


def test_python_and_lua_blend_mode_names_match() -> None:
    source = files("spa.kernel").joinpath("sprite_inspect.lua").read_text()
    table = source.split("local blend_modes = {", 1)[1].split("\n}", 1)[0]
    names = re.findall(r'\{ BlendMode\.[A-Z_]+, "([a-z_]+)" \}', table)
    assert len(names) == len(set(names))
    assert set(names) == set(get_args(BlendModeName))
