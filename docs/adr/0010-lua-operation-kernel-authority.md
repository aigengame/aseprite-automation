---
status: accepted
---

# Make packaged Lua handlers the authority for core operation behavior

This decision consolidates ADR-0011.

The versioned, packaged Lua Operation Kernel is the sole authority for each ordinary
Operation's Core Operation Semantics. One fixed handler defines what the Operation
creates, edits, observes, validates, converts, or exports through Aseprite. Standalone,
Plan, and application-composed execution invoke the same handlers.

Python owns the public contract and application orchestration: Operation Descriptors,
schemas, static Preflight, Execution Kind, Plan admission, failure mapping,
access-channel projection, selection and ordering of packaged handlers, process
invocation, staged commit, and Artifact reporting. It can compose packaged capabilities
through private protocol data, but it cannot reproduce their Aseprite behavior.

The Lua Kernel resolves live document targets, enforces document-dependent
preconditions, performs supported native mutations, observes native state, invokes
native conversion or export behavior, and produces the private protocol response.

SPA does not assemble or generate Lua source at runtime to implement an ordinary
Operation. Runtime request, response, staging, and diagnostic files carry data and
Artifacts rather than executable behavior. Ordinary handlers and shared helpers remain
packaged, versioned source.

Caller-owned raw Lua is a separate, explicitly unrestricted script-run capability. It
can be materialized unchanged when Aseprite requires a file, but it does not enter the
Kernel, participate in Operation Plans, inherit ordinary-operation guarantees, or
provide an internal alternate implementation path.
