# Use SPA through MCP

Install the optional MCP extra from [PyPI](https://pypi.org/project/aseprite-automation/):

```sh
uv tool install --python 3.13 'aseprite-automation[mcp]'
spa-mcp --help
```

Use `uv tool upgrade aseprite-automation` to update that installation. Configure the
client with the absolute `spa-mcp` path reported by your shell (`command -v spa-mcp`
on macOS/Linux).

For source development, install the extra from the checkout root:

```sh
uv sync --extra mcp
```

For the checkout installation, use the absolute path to `.venv/bin/spa-mcp`.
Ordinary CLI use does not require the MCP extra. Aseprite remains a separate install.

## Connect a local client

Configure a stdio server with these fields (replace both absolute paths):

```json
{
  "command": "/absolute/path/to/spa-mcp",
  "args": ["--aseprite", "/absolute/path/to/aseprite"]
}
```

For Codex, the equivalent server entry in the client's configuration is:

```toml
[mcp_servers.spa]
command = "/absolute/path/to/spa-mcp"
args = ["--aseprite", "/absolute/path/to/aseprite"]
startup_timeout_sec = 60
tool_timeout_sec = 120
```

The client starts the process; `spa-mcp` opens no network port. Protocol messages
use stdout and diagnostics use stderr. The default CLI is the `spa` bootstrap in
that same Python installation. `--spa /absolute/path/to/spa` explicitly selects
another installed CLI; the adapter uses it for discovery and all calls. It never
selects a second CLI implicitly through `PATH`.

`--aseprite` sets the CLI's default `SPA_ASEPRITE_EXECUTABLE`. Without the flag,
the existing environment and CLI discovery rules apply. A tool request may include
its schema-declared `aseprite` override. Paths use the adapter's working directory;
absolute Source, Target and Artifact paths are easiest to review.

Startup runs `spa schema`, which probes real Aseprite. A missing executable or
failed probe terminates with a diagnostic; it does not expose an empty tool list.
Restart after changing the installed SPA or default runtime to refresh discovery.

## Discover, call and inspect

Tools come from the installed Surface Manifest. For example, `spa sprite create`
becomes `sprite_create` and `spa export image` becomes `export_image`. Use each
published input schema to supply the complete Operation Request. No current Sprite
or workflow state carries across calls. The `schema` tool exposes applicable
Failure schemas and Capability Gaps.

The initial protocol target is `2026-07-28`, including `server/discover`. The same
SDK Server supports the separately tested `2025-11-25` legacy initialization path.
SPA does not add its own fallback or promise every historical protocol revision.

Successful tool calls return the unchanged Result as JSON text and structured
content. A SPA failure returns its complete Failure Envelope as JSON text with
`isError: true`; it is not forced into the success output schema. Process launch,
invalid CLI output and other adapter errors use an `adapter_error` diagnostic.
They are not SPA Failure Envelopes.

Verified PNG Artifacts also produce native MCP image content. The adapter checks
file size, SHA-256 and PNG format before sending the bytes. It only reads returned,
schema-declared Artifact fields; it offers no arbitrary path-reading tool. Other
Artifact formats retain their metadata.

A file removed or changed after export can prevent image projection. In that case,
`isError` is true, but the original successful Result remains in structured content
and JSON text. The additional diagnostic states `phase: content_projection` and
`operation_completed: true`. Inspect the completed outcome before taking another
action; a projection failure does not undo publication.

For the normal authoring loop and refusal handling, use the [SPA Skill](../skills/spa/SKILL.md).
Protocol, packaging and real-client evidence is recorded in
[issue #53 validation](evidence/issue-53-mcp.md).
