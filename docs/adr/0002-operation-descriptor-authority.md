---
status: accepted
---

# Use one Operation authority and a private Kernel Protocol

This decision consolidates ADR-0012.

Each public capability has one Operation Descriptor. It binds the Operation's public
request, result, and failure schemas to execution metadata and a packaged Lua handler.
The CLI command tree, MCP tools, and installed Surface Manifest are projections of
these descriptors; they do not maintain parallel capability registries.

Descriptors own registration and Published Language metadata, not native behavior.
Python contract types own public shapes and statically decidable invariants. The bound
Lua handler owns core Aseprite behavior as defined by ADR-0010.

The Aseprite adapter and Lua Operation Kernel communicate through a versioned private
Kernel Protocol. Public defaults and null semantics are resolved before transport, and
the adapter translates protocol values into the Published Language. Private
application orchestration can select and order packaged handlers, but it does not
create another public workflow language.

Every Kernel invocation returns an explicit protocol success or failure response.
Aseprite's process exit status and diagnostics are evidence used to classify the
outcome, not the public verdict by themselves.

This separation gives every access channel one public contract while allowing the
runtime protocol to evolve with delivered Operations. A new access channel consumes
the same descriptors or their installed Surface Manifest projection.
