---
status: accepted
---

# Prioritize the Core Domain and let functional requirements lead architecture growth

SPA's business capability is equivalent to Aseprite's: sprite creation, editing,
inspection, validation, conversion, and export. SPA adds the explicit control,
composition, observation, and verifiable feedback that agents need to use those
capabilities. These are functional capabilities even when Aseprite's interactive
editor does not expose the same automation form.

Sprite Automation is the Core Domain and has the highest delivery priority. Aseprite
Runtime Integration, Access Projection, and Asset Pipeline Integration are Supporting
Subdomains. Domain-neutral serialization, filesystem, process, and utility mechanisms
are Generic Subdomains or infrastructure. Supporting and Generic design follows
accepted Core Domain requirements, uses proportionate abstraction, and grows from
observed variation.

Behavior placement follows domain authority rather than deployment mechanics. Core
Operation Semantics remain Core behavior in their packaged Lua handlers; runtime
transport and resource discovery support that behavior. Staged commit and Artifact
verification are functional promises when an Operation depends on their observable
outcomes, while reusable filesystem mechanics remain technical support.

Non-functional work must trace to an accepted functional slice and an observed
operating need. It has no independent platform roadmap and does not justify speculative
infrastructure for scale, distribution, tenancy, governance, or compatibility.

The current CLI and local MCP path—stdio between client and adapter, with CLI subprocess
invocation behind the adapter—assume a trusted caller, workspace, packaged Operation set,
and Aseprite installation. The current delivery plan has no standalone REST API or remote
HTTP service. HTTP is not prohibited in principle: an accepted functional slice can add
bounded Artifact/resource access or MCP transport as an Access Projection over the same
Published Language and Application use cases.

SPA does not add authentication, accounts, roles, authorization policy, audit-history
storage, event sourcing, distributed consistency or locks, generalized recovery
infrastructure, service governance, multi-tenancy, or a generic sandbox without a
functional requirement and observed operating need. A future network-facing slice must
state the trust and deployment boundary it actually creates and add only the supporting
behavior required by that boundary. Per-operation evidence, native transactions, staged
commit, target addressing, process control, and diagnostics remain part of the
functional behavior they support rather than becoming such platforms.
