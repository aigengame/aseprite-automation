---
status: accepted
---

# Make the Operation Descriptor the single capability registration authority

SPA represents each public automation capability with one Operation Descriptor. The descriptor binds the Operation's request, result, and failure schemas to its execution metadata and packaged Lua handler. The CLI command tree, MCP tool surface, and Surface Manifest are projections derived from these descriptors; they do not maintain independent per-capability registries.

This preserves gda's architectural rule that one registration authority drives dispatch and schema projections, while adapting the name to SPA's domain language. In Aseprite, Command already means a native editor action exposed through `app.command`. Calling SPA's channel-neutral authority a Command Descriptor would conflate an SPA Operation, its CLI projection, and an Aseprite Command.

The descriptor is registration metadata rather than the home of operation behavior. Python contract types own public shape and static invariants; the packaged Lua handler owns the Operation's core Aseprite behavior. A descriptor identifies and connects those parts without duplicating their logic.

ADR-0010 further distinguishes this public registration authority from behavior authority: the descriptor owns the published contract and projections, while its bound Lua Operation Kernel handler is the sole implementation of the Operation's core Aseprite behavior.

Adding a parallel CLI, MCP, Surface Manifest, or Lua-handler registry is therefore an architectural violation. A new access channel must consume the same Operation Descriptors or the Surface Manifest projected from them.
