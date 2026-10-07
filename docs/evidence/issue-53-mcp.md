# Issue #53 MCP validation

## Environment and source

Validation date: 2026-10-07. Host: macOS arm64. Source implementation:
`8546a1ce8e667d70f5d17b74f8143132e8961d72`, based on dev
`af59411376d8e2caa7c9b8fe6c5e4d3f8eaf94c8`.

| Component | Observed version |
| --- | --- |
| Python | 3.13.13 |
| SPA wheel | 0.2.0, built from the source above |
| Official MCP Python SDK | 2.3.0 |
| Real client | codex-cli 0.154.0 |
| Aseprite | 1.3.18.5-dev, API 41 |

The four installed MCP production modules were compared byte for byte with the
source before the final client run. This is evidence for this host and runtime,
not a claim that Linux or every MCP client/version was tested.

## Automated checks

- `pytest tests/mcp -q`: **18 passed**, 29.49 seconds on the committed implementation.
- Explicit `2026-07-28` stdio: `server/discover`, `tools/list`, `tools/call`; no legacy
  fallback. Explicit legacy test negotiated `2025-11-25` and exercised success and
  a typed invalid-request failure through the same installed adapter.
- Real Manifest: 120 tools; every input/output schema equaled its installed
  Descriptor projection. The `schema` tool retained Failure schemas and Capability
  Gaps. Success text and structured JSON matched; typed failures validated against
  their CLI Failure schema and did not occupy structured success content.
- Real native workflow: create, inspect, validate and PNG export. Independent PNG
  decoding and a separate CLI reopen checked persisted output.
- Controlled CLI/filesystem checks: unavailable CLI/runtime; non-JSON or wrong-schema
  output with diagnostics; cancellation with a live or already-exited CLI leader;
  PNG content, missing files, wrong sizes/digests/formats, plural Artifacts and
  non-PNG metadata; no traversal of caller-owned nested JSON.
- Full fast suite before the final child-cleanup regression: **1958 passed,
  2374 deselected**, 338.53 seconds. The final focused suite above includes the added
  leader-exit regression. No full native suite or example rebuild was requested.
- Ruff lint/format, Pyright, `git diff --check`, wheel/sdist build and Twine checks
  passed. An isolated ordinary installation had no `mcp` module: `spa version`
  succeeded, while `spa-mcp` gave the optional-extra installation diagnostic.

The initial TDD stdio case failed because the entry point did not exist. Subsequent
red cases exposed an unvalidated malformed success, missing native ImageContent,
and cleanup that missed a native child after its CLI leader exited. Each was
replayed after its correction.

## Real Codex client

The final run used an ephemeral Codex invocation with a task-scoped stdio server;
no global MCP configuration or separate desktop chat was created. The selected
server command was the isolated installed `spa-mcp`, with the real Aseprite path
passed through `--aseprite`. The client used its default model. It called:

1. `sprite_create`: 3×2 RGB, one opaque Background of RGBA (17,34,51,255), new Target.
2. `sprite_get`: inspect the saved file's Frames and Layers.
3. `sprite_validate`: expected width 3, height 2, RGB, one Frame.
4. `export_image`: Frame 1, full Canvas, visible Layers, preserved composition,
   mode, profile and transparency, new PNG destination.

All calls completed and returned successful structured Results. The actual inputs
and outputs passed the selected installed CLI request/result schemas. Each JSON
text item parsed identically to its structured Result. The Codex event stream
contained a native `image/png` ImageContent item for the export, and Codex confirmed
that it received the image.

| Independent check | Result |
| --- | --- |
| Editable Sprite bytes | 1,019; size and digest matched `target_commit` |
| Separate native reopen | 3×2 RGB, one Frame, one Background Layer and Cel |
| PNG / decoded ImageContent / Artifact | Same 91 bytes |
| PNG SHA-256 | `de663d28f52704964bdc989a04ff941e64b863b3f977c6b8f538b959b827c9ab` |
| Independent Pillow pixels | Six pixels, all RGBA (17,34,51,255) |

Codex's event JSONL does not expose its negotiated MCP revision. The explicit
modern/legacy protocol assertions above come from SDK stdio tests, not an inferred
Codex revision. The local transcript is `codex-events-final-8546a1c.jsonl` in the
implementation's temporary consumer directory; `verification.json` records the
checks. Large transcripts and generated binary assets are not repository fixtures.

The reproducible client pattern is `codex exec --ephemeral --ignore-user-config`
with a task-scoped `mcp_servers.spa` configuration as shown in [MCP usage](../mcp.md).
For this unattended test, Codex's `--approve-for-me` review policy permitted the
bounded calls; policy `never` rejected them before server execution. The host also
needed its existing system-proxy feature when ignoring user configuration. Those
are client/environment settings, not new SPA options or support promises.

## Limits

Linux Native E2E was not dispatched. The prior GitHub billing failure does not
invalidate local evidence or become a successful CI claim. PR checks report their
own current status. No workflow triggers, budgets, protocol compatibility matrix,
HTTP service or example-rebuild policy changed.
