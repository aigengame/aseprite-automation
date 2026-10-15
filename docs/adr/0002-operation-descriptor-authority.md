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

Each Descriptor's `help_summary` owns the Operation's purpose description. CLI
help, the Surface Manifest, and MCP tools project that text. Request and Result
models own field descriptions and constraints. CLI Access owns root and Command
Group introductions; group identity and hierarchy still derive from Operation
paths. Presentation text does not register capabilities.

Published schemas use Pydantic's generation hooks to omit automatic titles that
repeat field or model names. Authored descriptions, useful titles, defaults,
examples, and constraints remain. Each entry publishes its Request once in
`request_schema`; `invocation_schema` owns CLI bindings and stdin guidance.
Failure schemas share the Envelope fields and use standard JSON Schema `oneOf`
branches to bind each Code to its Category and typed Details. Each schema retains
its local definitions and works with a standard validator. There is no separate
schema registry or reference-resolution protocol.

Bare `spa`, `spa --help`, and `spa help` show the same root help and exit zero.
`spa help <command path>` navigates the generated command tree and renders the
target's help without executing an Operation or probing Aseprite. Unknown paths
and excess path components use the existing Access-level Failure Envelope.
`help` is CLI navigation, not an Operation or MCP tool.

Descriptors own registration, public shapes, Published Language metadata, and
statically decidable contract invariants, not native behavior. Python contract types
implement and validate those Descriptor-owned shapes; they are not a second contract
authority. An Ordinary Core Operation binds one fixed packaged Lua handler. Its fixed
packaged semantic entry point owns Core Operation Semantics and native mapping as
defined by ADR-0010. A capability implemented by an Application use case can have no
Kernel binding. An Operation Plan selects and orders the same packaged semantic entry
points through its fixed Plan handler without redefining their semantics.

A runtime-backed Descriptor declares the Lua language profile, minimum Aseprite
`app.apiVersion`, and Aseprite-provided capabilities required by that Operation. The
Aseprite Adapter observes those facts from the selected process. A complete probe
establishes the scripting, file I/O, and JSON facilities used by its own transport; a
failure before that response uses the typed process or Kernel failure channel. The
Adapter reports native runtime capabilities independently of those fixed
prerequisites. For an ordinary Operation, the Application checks the observed Lua
language, API version, and capabilities against its Descriptor before execution.
An Operation Plan derives requirements from its selected Step Descriptors plus the
mandatory final Sprite inspection and observes and checks them inside its one Aseprite
process before the first Step. The fixed Plan handler reports incompatible facts through
the typed Kernel Protocol; Application maps
them to `runtime_incompatible`. This avoids a second Aseprite probe process while
preserving the pre-Step gate and zero Target Commit on incompatibility. Aggregate
discovery declares the complete Plan Step repertoire supported only when all eligible
Step requirements are observed. An individual Plan can use a subset and is checked
against its selected Step requirements plus final Sprite inspection. Aseprite product
version remains provenance and does not replace runtime observations.

Discovery derives availability and Capability Gaps from the complete internal
Runtime Observation. Its public Runtime Facts contain the canonical executable,
selection source, resource status, versions, prerequisites, and capabilities.
Resolution intermediates and raw Convolution probe payloads remain internal;
the public Gap reports the current restriction and useful next action through its
feature-owned `reason`. Discovery, human output, MCP, and applicable failure messages
and nested details reuse that reason. Public help and schema descriptions follow the
same boundary: internal research, Baseline Aseprite attribution, raw probes, and
implementation references remain in ordinary comments or maintenance documentation.

The Baseline Aseprite definition is `SPA_BASELINE_ASEPRITE_VESION` in
`src/spa/__init__.py`. For other releases,
SPA follows [Aseprite's native scripting compatibility policy](https://github.com/aseprite/api/blob/main/Changes.md)
under [PRD #1](https://github.com/aigengame/aseprite-automation/issues/1)
and [issue #132](https://github.com/aigengame/aseprite-automation/issues/132).
SPA has no independent Aseprite-version allowlist, release-by-release test matrix,
or guarantee of unchanged native behavior. The Descriptor checks above establish
the requirements needed to execute an Operation, not semantic parity across
untested Aseprite releases. An observed incompatibility is assessed for its
affected Operation; a hypothetical later release alone is not an acceptance gate.
Feature-delivery evidence and checks for claimed host execution profiles remain.

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
