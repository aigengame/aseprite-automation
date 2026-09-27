---
status: accepted
---

# Make packaged Lua handlers the authority for core operation behavior

This decision consolidates ADR-0011.

Under [ADR-0095](0095-asset-preparation-authoring-and-delivery.md), Ordinary Core
Operation and Core Operation Semantics remain execution terms, independent of
strategic Subdomain classification. Native Asset Delivery Operations retain the same
authority and guarantees. A wholly Application-owned capability does not require a
native handler for non-native facts; native transformations it invokes still follow
this decision.

The versioned, packaged Lua Operation Kernel is the sole authority for each Ordinary
Core Operation's Core Operation Semantics. Fixed packaged semantic entry points define
what an Operation creates, edits, observes, validates, converts, or exports through
Aseprite. Standalone handlers and the Plan handler call these same entry points.
Standalone handlers save and reopen their own Operation output. The Plan handler keeps
one Sprite live across Steps and performs one final save-and-reopen verification before
Target Commit.

The Python Application layer validates requests and outcomes against the
Descriptor-owned public contract and owns application orchestration: contract-type
validation, static Preflight, Plan admission, failure mapping, selection and ordering
of packaged handlers, Target Commit coordination, and Artifact reporting. It supplies
Descriptor-backed Application entry points for Access adapters to project and requests
Aseprite execution through an inner-owned port. Access adapters own access-channel
projection. The Aseprite Adapter owns process launch, Kernel transport, and
invocation mechanics. Application can compose packaged capabilities through private
protocol data, but it cannot reproduce their Aseprite behavior or become a second
public-contract authority.

The Lua Kernel resolves live document targets, enforces document-dependent
preconditions, performs supported native mutations, observes native state, invokes
native conversion or export behavior, and produces the private protocol response.

SPA does not assemble or generate Lua source at runtime to implement an Ordinary Core
Operation. Runtime request, response, staging, and diagnostic files carry data and
Artifacts rather than executable behavior. Ordinary Core Operation handlers and shared
helpers remain packaged, versioned source.

Packaged Kernel handlers currently target the `Lua 5.4` language profile. They do not
depend on an external Lua interpreter, LuaJIT extensions, precompiled Lua bytecode, or
unverified native Lua modules. Each handler's Operation Descriptor narrows the
Aseprite API capabilities required for its native behavior.

The first macOS evidence profile is Aseprite 1.3.18.5-dev with `app.apiVersion == 41`;
that build vendors Lua 5.4.6. The patch release records provenance for that build. The
handler contract remains the `Lua 5.4` language profile observed through `_VERSION`,
not a dependency on a system Lua installation or a universal Lua patch version.

Caller-owned raw Lua is a separate, explicitly unrestricted script-run capability. It
can be materialized unchanged when Aseprite requires a file, but it does not enter the
Kernel, participate in Operation Plans, inherit Ordinary Core Operation guarantees, or
provide an internal alternate implementation path. SPA descriptor registration,
identity resolution, and Ordinary Core Operation dispatch cannot treat `script run` as
a replacement, override, rewrite, or proxy for an existing Ordinary Core Operation.
SPA cannot route an Ordinary Core Operation through `script run` to bypass its Descriptor, Preflight,
packaged handler, Postconditions, validation, or result and failure contract. A caller
can still execute arbitrary Lua through `script run`, but that execution stays outside
the Ordinary Core Operation contract and has no sandbox claim.
