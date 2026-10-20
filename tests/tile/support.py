"""Native Tile fixture builders and Tile request values."""

from pathlib import Path

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.support import process_diagnostics

FIXTURES = Path(__file__).parent / "fixtures"


def tiles_sprite(runtime: RuntimeObservation, source: Path, **params: object) -> None:
    """Write the shared-Tileset Tilemap Sprite of `tiles.lua` to source."""
    lua = run_lua(FIXTURES / "tiles.lua", runtime, source=source, **params)
    assert lua.returncode == 0, process_diagnostics(lua)


def lifecycle_sprite(
    runtime: RuntimeObservation, source: Path, **params: object
) -> None:
    """Write the keyed Tile lifecycle Sprite of `lifecycle.lua` to source."""
    lua = run_lua(FIXTURES / "lifecycle.lua", runtime, source=source, **params)
    assert lua.returncode == 0, process_diagnostics(lua)


def lifecycle_limits_sprite(
    runtime: RuntimeObservation, source: Path, **params: object
) -> None:
    """Write the Tile lifecycle bound Sprite of `lifecycle_limits.lua` to source."""
    lua = run_lua(FIXTURES / "lifecycle_limits.lua", runtime, source=source, **params)
    assert lua.returncode == 0, process_diagnostics(lua)


def verify_lifecycle(
    runtime: RuntimeObservation, source: Path, **params: object
) -> None:
    """Check the native Tiles of source with `verify_lifecycle.lua`.

    The fixture exits with an error when a check fails.
    """
    lua = run_lua(FIXTURES / "verify_lifecycle.lua", runtime, source=source, **params)
    assert lua.returncode == 0, process_diagnostics(lua)


def cel_creation_sprite(
    runtime: RuntimeObservation, source: Path, **params: object
) -> None:
    """Write the Tilemap Cel creation Sprite of `cel_creation.lua` to source."""
    lua = run_lua(FIXTURES / "cel_creation.lua", runtime, source=source, **params)
    assert lua.returncode == 0, process_diagnostics(lua)


def verify_cel_creation(
    runtime: RuntimeObservation, source: Path, result: Path, **params: object
) -> None:
    """Check the added Tilemap Cels of result against source with `cel_creation.lua`.

    The fixture exits with an error when a check fails.
    """
    lua = run_lua(
        FIXTURES / "cel_creation.lua", runtime, source=source, result=result, **params
    )
    assert lua.returncode == 0, process_diagnostics(lua)


def verify_tileset_lifecycle(
    runtime: RuntimeObservation, source: Path, **params: object
) -> None:
    """Check the rebound Tilemap Layers of source with `verify_tileset_lifecycle.lua`.

    The fixture exits with an error when a check fails.
    """
    lua = run_lua(
        FIXTURES / "verify_tileset_lifecycle.lua", runtime, source=source, **params
    )
    assert lua.returncode == 0, process_diagnostics(lua)


def snapshot(mode: str = "rgb", *, transparent: bool = False) -> dict:
    color = {
        "rgb": {
            "kind": "rgba",
            "red": 0 if transparent else 17,
            "green": 0 if transparent else 29,
            "blue": 0 if transparent else 41,
            "alpha": 0 if transparent else 255,
        },
        "grayscale": {
            "kind": "grayscale",
            "gray": 0 if transparent else 79,
            "alpha": 0 if transparent else 255,
        },
        "indexed": {"kind": "palette-index", "index": 7 if transparent else 2},
    }[mode]
    return {
        "coordinate_space": "image-pixel",
        "color_mode": mode,
        "rectangle": {"x": 0, "y": 0, "width": 2, "height": 3},
        "rows": [[{"length": 2, "color": color}] for _ in range(3)],
    }
