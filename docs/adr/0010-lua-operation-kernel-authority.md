---
status: accepted
---

# Make packaged Lua handlers the authority for core operation behavior

This decision consolidates ADR-0011.

The versioned, packaged Lua Operation Kernel is the sole authority for each Ordinary
Core Operation's Core Operation Semantics. One fixed handler defines what the Operation
creates, edits, observes, validates, converts, or exports through Aseprite. Standalone,
Plan, and application-composed execution invoke the same handlers.

The Python Application layer validates requests and outcomes against the
Descriptor-owned public contract and owns application orchestration: contract-type
validation, static Preflight, Plan admission, failure mapping, selection and ordering
of packaged handlers, staged-commit coordination, and Artifact reporting. It supplies
Descriptor-backed Application entry points for Access adapters to project and requests
Aseprite execution through an inner-owned port. Access adapters own access-channel
projection. The Aseprite Runtime adapter owns process launch, Kernel transport, and
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
