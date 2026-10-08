---
status: accepted
---

# Project installed CLI contracts through the MCP SDK

## Context

Agents need the same explicit SPA Operations through MCP, including native image
content for visual inspection. Operation Descriptors already own public schemas,
execution metadata and failure meanings. An MCP Adapter must not become another
Operation registry, native executor or current-document session.

## Decision

Use the official MCP Python SDK 2.x low-level Server. The current protocol target
is `2026-07-28`: requests carry their inputs, and `server/discover` does not create
an application session. The same SDK handles the separately tested legacy
`2025-11-25` initialization path. SPA adds no protocol negotiation or compatibility
implementation of its own.

The optional `spa-mcp` entry point uses local stdio. It discovers the selected
installed CLI through `spa schema` and uses that same CLI and default Aseprite
configuration for subsequent calls. Startup discovery must succeed before the
server exposes tools. Each tool name retains a mapping to its exact Operation;
input and success output schemas are unchanged Manifest projections. Duplicate
projected names fail discovery instead of replacing an Operation.

The CLI receives complete JSON requests on stdin. It remains responsible for
validation, native work and publication. MCP returns the unchanged success Result
as structured content and JSON text, or the complete CLI Failure Envelope as JSON
text with `isError`. Adapter failures have a distinct diagnostic shape and do not
invent SPA failure codes. Process cancellation cleans up the CLI and its native
child on the supported macOS/Linux hosts.

Only schema-declared Result Artifact fields supply local image content. PNG bytes
must match the returned size, digest and format before projection as ImageContent.
Other formats keep their metadata. If content projection fails after CLI success,
the response keeps the completed Result and explicitly identifies the projection
failure. It does not claim rollback or recommend repeating a mutation.

## Consequences

CLI invocation and outcome projection are separate from stdio wiring, so a future
accepted Streamable HTTP transport can reuse them. It would need its own concrete
client, file-access and deployment requirements. This slice creates no HTTP/REST
service, resource browser, file server, session store or general transport framework.
These delivery boundaries remain open to accepted future needs.

The ordinary CLI does not import or require MCP. The extra adds an SDK dependency;
SDK-native legacy interoperability is bounded evidence, not an all-version support
promise. Restarting the adapter refreshes its installed tool surface after changing
SPA or its default runtime. Per-request Aseprite overrides keep existing CLI meaning
and are still checked by the selected Operation.

[Issue #53](https://github.com/aigengame/aseprite-automation/issues/53) owns feature
acceptance. [MCP usage](../mcp.md) documents installation and invocation. This decision
applies [ADR-0002](0002-operation-descriptor-authority.md) and
[ADR-0013](0013-result-and-failure-contract.md); it does not redefine their contracts.
