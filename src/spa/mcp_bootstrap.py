"""Optional stdio MCP composition root; ordinary CLI imports no MCP dependency."""

import argparse
import json
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Expose the installed SPA surface over MCP stdio."
    )
    parser.add_argument(
        "--spa", help="SPA executable (default: this Python installation)."
    )
    parser.add_argument(
        "--aseprite", help="Default Aseprite executable; requests may override it."
    )
    args = parser.parse_args()
    try:
        import anyio
        from mcp.server.stdio import stdio_server

        from spa.access.mcp.cli import AdapterError, Cli
        from spa.access.mcp.server import build_server
    except ModuleNotFoundError as exc:
        parser.exit(2, f"spa-mcp requires aseprite-automation[mcp]: {exc}\n")
    environment = os.environ.copy()
    if args.aseprite:
        environment["SPA_ASEPRITE_EXECUTABLE"] = args.aseprite
    command = (
        [args.spa]
        if args.spa
        else [sys.executable, "-c", "from spa.bootstrap import main; main()"]
    )

    async def serve() -> None:
        server = await build_server(Cli(command, environment))
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    try:
        anyio.run(serve)
    except AdapterError as exc:
        print(json.dumps({"adapter_error": exc.diagnostics}), file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        raise SystemExit(130) from None
