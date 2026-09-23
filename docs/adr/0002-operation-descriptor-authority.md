---
status: accepted
---

# Use one Operation authority and a private Kernel Protocol

This decision consolidates ADR-0012.

Each structured public capability has one Operation Descriptor. It binds the
capability's public request, result, and failure schemas to execution metadata and a
declared execution definition. The CLI command tree, eligible MCP tools, and Operation
entries in the installed Surface Manifest are projections of these descriptors; they
do not maintain parallel capability registries. CLI failures before a Descriptor can
be selected use the shared public Failure Code registration under ADR-0013, not a
synthetic Operation.

Descriptors own registration, public shapes, Published Language metadata, and
statically decidable contract invariants, not native behavior. Python contract types
implement and validate those Descriptor-owned shapes; they are not a second contract
authority. An Ordinary Core Operation binds one fixed packaged Lua handler, which owns
its Core Operation Semantics and native mapping as defined by ADR-0010. A capability
whose behavior is implemented by an Application use case can have no Kernel binding. An
application-composed capability can select and order multiple packaged Ordinary Core
Operation handlers without redefining their semantics.

A runtime-backed Descriptor declares the Lua language profile, minimum Aseprite
`app.apiVersion`, and Aseprite-provided capabilities required by that Operation. The
Aseprite Adapter observes those facts from the selected process. A complete probe
establishes the scripting, file I/O, and JSON facilities used by its own transport; a
failure before that response uses the typed process or Kernel failure channel. The
Adapter reports native runtime capabilities independently of those fixed
prerequisites. For an ordinary Operation, the Application checks the observed Lua
language, API version, and capabilities against its Descriptor before execution.
An Operation Plan derives requirements from its eligible Step Descriptors and observes
and checks them inside its one Aseprite process before the first Step. The fixed Plan
handler reports incompatible facts through the typed Kernel Protocol; Application maps
them to `runtime_incompatible`. This avoids a second Aseprite probe process while
preserving the pre-Step gate and zero Target Commit on incompatibility. Aseprite product
version remains provenance and does not replace runtime observations.

The Aseprite Adapter and Lua Operation Kernel communicate through a versioned private
Kernel Protocol. Public defaults and null semantics are resolved before transport.
The adapter decodes private Kernel Protocol responses and reports typed runtime
evidence; the Application validates and classifies that evidence into the Published
Language under ADR-0013. Neither layer reimplements packaged Core Operation
Semantics. Private application orchestration can select and order packaged handlers,
but it does not create another public workflow language.

Before SPA 1.0, the co-packaged Aseprite Adapter and Lua Kernel support only their
current Kernel Protocol version. The version field checks an exact match for one
invocation; it does not promise cross-release compatibility. The pair may change the
protocol incompatibly between pre-1.0 releases. During that period, SPA does not
negotiate or migrate historical protocol messages, retain old Kernel implementations
or a runtime version registry, or provide protocol replay. This does not waive
compatibility checks against the installed Aseprite Lua runtime and scripting API.

Every Kernel invocation returns an explicit Kernel Protocol success or failure
response.
Aseprite's process exit status and diagnostics are evidence used to classify the
outcome, not the public verdict by themselves.

This separation gives every access channel one public contract while allowing the
Kernel Protocol to evolve with delivered Operations. A new access channel consumes
the same descriptors or their installed Surface Manifest projection.
