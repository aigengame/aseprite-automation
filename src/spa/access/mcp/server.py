"""Project installed Operation schemas and outcomes into MCP tools."""

import re
from importlib.metadata import version

from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.types import (
    INVALID_PARAMS,
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    Tool,
)

from spa.access.mcp.cli import AdapterError, Cli
from spa.access.mcp.content import adapter_failure, project_outcome


async def build_server(cli: Cli) -> Server:
    discovered = await cli.invoke("spa schema", {})
    if discovered.exit_status or discovered.payload.get("status") != "success":
        raise AdapterError(
            "SPA discovery failed",
            stdout=discovered.stdout,
            stderr=discovered.stderr,
            exit_status=discovered.exit_status,
        )
    entries = {}
    tools = []
    try:
        for entry in discovered.payload["operations"]:
            operation = entry["operation"]
            if not re.fullmatch(r"spa [a-z][a-z0-9-]*( [a-z][a-z0-9-]*)*", operation):
                raise ValueError(f"Invalid Operation identity: {operation}")
            name = operation[4:].replace(" ", "_").replace("-", "_")
            if name in entries:
                raise ValueError(f"Duplicate MCP tool name: {name}")
            entries[name] = entry
            tools.append(
                Tool(
                    name=name,
                    description=operation,
                    input_schema=entry["request_schema"],
                    output_schema=entry["result_schema"],
                    _meta={
                        "spa": {
                            key: entry[key]
                            for key in ("execution_kind", "determinism", "side_effects")
                            if key in entry
                        }
                    },
                )
            )
        if not tools:
            raise ValueError("No callable Operations")
    except (KeyError, TypeError, ValueError) as exc:
        raise AdapterError(
            "Unusable SPA Surface Manifest",
            reason=str(exc),
            stdout=discovered.stdout,
            stderr=discovered.stderr,
        ) from exc

    async def list_tools(
        ctx: ServerRequestContext, params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        return ListToolsResult(tools=tools)

    async def call_tool(
        ctx: ServerRequestContext, params: CallToolRequestParams
    ) -> CallToolResult:
        if params.name not in entries:
            raise MCPError(INVALID_PARAMS, f"Unknown SPA tool: {params.name}")
        try:
            outcome = await cli.invoke(
                entries[params.name]["operation"], params.arguments or {}
            )
            return project_outcome(outcome, entries[params.name])
        except AdapterError as exc:
            return adapter_failure(exc)

    return Server(
        "spa",
        version=version("sprite-automation"),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )
