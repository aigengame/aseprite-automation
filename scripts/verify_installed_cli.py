"""Smoke test a wheel-installed SPA executable against project metadata."""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_installed_cli.py /path/to/spa")

    executable = Path(sys.argv[1])
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    expected_version = metadata["project"]["version"]
    completed = subprocess.run(
        [str(executable), "version"],
        check=True,
        capture_output=True,
        text=True,
    )
    response = json.loads(completed.stdout)
    expected = {
        "status": "success",
        "operation": "spa version",
        "spa_version": expected_version,
    }
    if response != expected:
        raise SystemExit(f"installed CLI returned {response!r}; expected {expected!r}")

    installed_python = executable.parent / (
        "python.exe" if os.name == "nt" else "python"
    )
    subprocess.run(
        [
            str(installed_python),
            "-c",
            """from importlib.resources import files
kernel = files("spa.kernel")
for name in (
    "probe.lua",
    "sprite_create.lua",
    "sprite_create_support.lua",
    "sprite_get.lua",
    "sprite_inspect.lua",
    "sprite_flatten.lua",
    "sprite_geometry.lua",
    "sprite_persistence.lua",
    "layer_add.lua",
    "layer_get.lua",
    "layer_select.lua",
    "layer_mutate.lua",
    "layer_mutation_support.lua",
    "digest.lua",
    "sprite_inspection_fixture.aseprite",
    "paint_apply_fixture.aseprite",
    "frame_mutate.lua",
    "frame_get.lua",
    "frame_support.lua",
    "tag_mutate.lua",
    "tag_support.lua",
    "tag_select.lua",
    "tag_get.lua",
    "image_get.lua",
    "image_replace.lua",
    "image_snapshot.lua",
    "layer_composition.lua",
    "raster_color.lua",
    "export_image.lua",
    "export_image_support.lua",
):
    resource = kernel.joinpath(name)
    if not resource.is_file() or not resource.read_bytes():
        raise SystemExit(f"missing installed Kernel resource: {name}")
    if resource.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise SystemExit(f"unresolved Git LFS pointer in installed Kernel resource: {name}")
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    print(
        f"verified installed SPA {expected_version} and Kernel resources at "
        f"{executable}"
    )


if __name__ == "__main__":
    main()
