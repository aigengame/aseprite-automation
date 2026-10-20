"""Sprite builders and Image reads shared by the native Paint tests."""

import json
from pathlib import Path

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run_lua
from tests.support import process_diagnostics

FIXTURES = Path(__file__).parent / "fixtures"

RED = {"kind": "rgba", "red": 255, "green": 0, "blue": 0, "alpha": 255}


def create_sprite(target: Path, *, width: int = 8, height: int = 6) -> None:
    """Create a transparent RGB Sprite of the given size at target."""
    expect_success(
        "sprite create",
        {
            "target_sprite_file": str(target),
            "width": width,
            "height": height,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )


def native_fixture(
    runtime: RuntimeObservation,
    tmp_path: Path,
    *,
    reference: bool = False,
    **options: object,
) -> tuple[Path, Path]:
    """Write the native Paint source Sprite and, on request, its reference.

    The fixture reads the options, with the `rgb` mode by default, from one JSON
    file. The reference holds the direct `app.useTool` result for the options.
    """
    source = tmp_path / "source.aseprite"
    expected = tmp_path / "reference.aseprite"
    config = tmp_path / "native.json"
    config.write_text(json.dumps({"mode": "rgb", **options}))
    params: dict[str, object] = {"input": config, "source": source}
    if reference:
        params["reference"] = expected
    lua = run_lua(FIXTURES / "native_paint_reference.lua", runtime, **params)
    assert lua.returncode == 0, process_diagnostics(lua)
    return source, expected


def read_pixels(
    sprite: Path, *, frame: int = 1, size: tuple[int, int] = (8, 6)
) -> list[list[dict]]:
    """Read the Layer 1 Image of one Frame as rows of colors, from the origin."""
    result = expect_success(
        "image get",
        {
            "sprite_file": str(sprite),
            "source": {
                "kind": "individual",
                "target": {"layer": {"layer_path": [1]}, "frame_number": frame},
                "rectangle": {"x": 0, "y": 0, "width": size[0], "height": size[1]},
            },
        },
    )
    return [
        [run["color"] for run in row for _ in range(run["length"])]
        for row in result["snapshot"]["rows"]
    ]
