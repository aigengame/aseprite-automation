"""Packaged Kernel resources of runtime capability probes and Operation handlers."""

import sys
from importlib.resources import files

import pytest

from spa.application.surface import OPERATIONS, PROBE_RESOURCES
from spa.contracts.ports import PackagedHandler, PackagedResource


@pytest.mark.parametrize(
    "path",
    [
        "../probe.lua",
        "/probe.lua",
        "runtime/../probe.lua",
        "runtime//probe.lua",
        "runtime\\probe.lua",
        "runtime/./probe.lua",
        "runtime/probe.py",
    ],
)
def test_packaged_paths_remain_relative_fixed_resources(path: str) -> None:
    with pytest.raises(ValueError):
        PackagedResource("probe", path)
    with pytest.raises(ValueError):
        PackagedHandler("probe", path)


def test_resource_parameters_remain_independent_of_package_paths() -> None:
    resource = PackagedResource("inspection", "document/sprite/sprite_inspect.lua")
    handler = PackagedHandler(
        "sprite_get", "document/sprite/sprite_get.lua", (resource,)
    )
    assert handler.support_resources[0].parameter_name == "inspection"
    with pytest.raises(ValueError):
        PackagedHandler("document/sprite_get", handler.package_path)
    with pytest.raises(ValueError):
        PackagedHandler("sprite_get", handler.package_path, (resource, resource))


def test_probe_and_handler_resources_are_packaged() -> None:
    kernel = files("spa.kernel")
    # Each handler is a module value of the module that defines its execute function.
    handlers = {
        value
        for descriptor in OPERATIONS
        for value in vars(sys.modules[descriptor.execute.__module__]).values()
        if isinstance(value, PackagedHandler)
    }
    assert handlers
    paths = {resource.package_path for resource in PROBE_RESOURCES}
    for handler in handlers:
        paths.add(handler.package_path)
        paths.update(resource.package_path for resource in handler.support_resources)

    for name in sorted(paths):
        resource = kernel.joinpath(name)
        assert resource.is_file(), name
        assert len(resource.read_bytes()) > 0, name


def test_paint_capability_probe_has_no_sprite_capability_gate() -> None:
    probe = (
        files("spa.kernel")
        .joinpath("runtime/capability_probe.lua")
        .read_text(encoding="utf-8")
    )
    paint_probe = probe.split("local function observes_paint_apply()", 1)[1].split(
        "function module.observe()", 1
    )[0]

    assert "creation.execute" not in paint_probe
    assert "inspection" not in paint_probe
    assert "if observes_paint_apply() then" in probe
