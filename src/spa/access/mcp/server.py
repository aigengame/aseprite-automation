"""Project installed Operation schemas and outcomes into MCP tools."""

import json
import re

from jsonschema import Draft202012Validator, ValidationError
from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.types import (
    INVALID_PARAMS,
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from spa.access.mcp.cli import AdapterError, Cli


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
            for field in ("request_schema", "result_schema", "failure_schema"):
                Draft202012Validator.check_schema(entry[field])
            entries[name] = entry
            tools.append(
                Tool(
                    name=name,
                    description=operation,
                    input_schema=entry["request_schema"],
                    output_schema=entry["result_schema"],
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
            entry = entries[params.name]
            schema = entry[
                "result_schema" if outcome.exit_status == 0 else "failure_schema"
            ]
            try:
                Draft202012Validator(schema).validate(outcome.payload)
            except ValidationError as exc:
                raise AdapterError(
                    "SPA output does not match its published schema",
                    reason=exc.message,
                    stdout=outcome.stdout,
                    stderr=outcome.stderr,
                    exit_status=outcome.exit_status,
                ) from exc
        except AdapterError as exc:
            return CallToolResult(
                is_error=True,
                content=[
                    TextContent(
                        type="text", text=json.dumps({"adapter_error": exc.diagnostics})
                    )
                ],
            )
        return CallToolResult(
            is_error=outcome.exit_status != 0,
            structured_content=outcome.payload if outcome.exit_status == 0 else None,
            content=[TextContent(type="text", text=outcome.stdout)],
        )

    return Server("spa", on_list_tools=list_tools, on_call_tool=call_tool)
