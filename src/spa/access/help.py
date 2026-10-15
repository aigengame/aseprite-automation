"""CLI navigation and introductions; Operation descriptions belong to Descriptors."""

from typing import Annotated

import typer
from typer.core import TyperGroup

ROOT_HELP = "Aseprite automation for AI agents."
ROOT_EPILOG = (
    "Operations emit JSON by default. Add --human after a command for readable "
    "output, for example: spa info --human. --json takes precedence if both are set. "
    "Use spa help COMMAND... to explore commands."
)
GROUP_HELP = {
    "script": "Run caller-owned Lua scripts in Aseprite.",
    "sprite": "Create, inspect, validate, and transform Sprite documents.",
    "layer": "Inspect and edit the Layer hierarchy and properties.",
    "paint": "Draw, fill, and composite pixels in Cel Images.",
    "filter": "Apply native color and pixel filters.",
    "selection": "Build, transform, and inspect Selection masks.",
    "frame": "Inspect and edit animation Frames.",
    "cel": "Inspect and edit Cels, their Images, and links.",
    "motion": "Apply a motion recipe across Frames.",
    "image": "Read, replace, import, and transform Cel Images.",
    "raster": "Prepare external raster assets for Sprite authoring.",
    "tag": "Inspect and edit animation Tags.",
    "slice": "Inspect and edit Slices and their frame-specific bounds.",
    "palette": "Inspect, edit, import, and export Palettes.",
    "export": "Export images, animations, Sprite Sheets, and Tilesets.",
    "animation": "Audit, compare, and preview animation Frames.",
    "plan": "Check or execute an Operation Plan for one Sprite.",
    "tileset": "Inspect and manage Tilesets and their Tiles.",
    "tileset tile": "Inspect and edit individual Tiles and their order.",
    "tilemap": "Inspect, validate, and edit Tile Cells in Tilemap Cels.",
}


def root_help(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def show_help(
    ctx: typer.Context,
    command_path: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="COMMAND...", help="Command path, for example: tileset tile add."
        ),
    ] = None,
) -> None:
    """Show help for SPA, a command group, or a command."""
    current = ctx.find_root()
    parts = command_path or []
    for part in parts:
        command = current.command
        target = (
            command.get_command(current, part)
            if isinstance(command, TyperGroup)
            else None
        )
        if target is None:
            raise typer.BadParameter(
                f"Unknown command path: {' '.join(parts)}",
                ctx=ctx,
                param_hint="COMMAND",
            )
        current = typer.Context(target, info_name=part, parent=current)
    typer.echo(current.get_help())
