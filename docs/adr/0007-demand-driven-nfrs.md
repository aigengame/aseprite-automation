---
status: accepted
---

# Prioritize the Core Domain and let functional requirements lead architecture growth

SPA's business capability is equivalent to Aseprite's: sprite creation, editing,
inspection, validation, conversion, and export. SPA adds the explicit control,
composition, observation, and verifiable feedback that agents need to use those
capabilities. These are functional capabilities even when Aseprite's interactive
editor does not expose the same automation form.

[ADR-0095](0095-asset-preparation-authoring-and-delivery.md) refines this decision's
original Sprite Automation Core classification: Sprite Authoring is the Core Domain;
Asset Preparation and Asset Delivery are Supporting Subdomains alongside Aseprite
Runtime Integration, Access Projection, and Asset Pipeline Integration. `CONTEXT.md`
owns the current strategic model. Domain-neutral serialization, filesystem, and
utility mechanisms remain Generic. Aseprite process execution, invocation policy,
diagnostic capture, and process wrappers remain Aseprite Runtime Integration.
The Core has the highest modeling and delivery priority. Supporting and Generic
design follows accepted functional requirements, uses proportionate abstraction,
and grows from observed variation.

The Aseprite Adapter prepares each process invocation under Runtime Integration.
This private boundary can select an operating-system and installation-specific launch
path, connect required Aseprite resources, and provide an isolated writable user
folder. It keeps the installed executable's canonical identity separate from the
process launch path. It does not own Sprite or Artifact paths, alter an installation,
or escape the caller's execution restrictions. A restricted-environment support claim
requires a real Aseprite integration check in that environment; one host strategy
does not establish support for another operating system or sandbox.

Behavior placement follows domain authority rather than deployment mechanics. The
established Core Operation Semantics execution model applies to native Operations in
both Core and Supporting Subdomains; their packaged Lua handlers retain authority.
Runtime transport and resource discovery support that behavior. Staged commit and Artifact
verification are functional promises when an Operation depends on their observable
outcomes, while reusable filesystem mechanics remain technical support.

Non-functional work must trace to an accepted functional slice and an observed
operating need. It has no independent platform roadmap and does not justify speculative
infrastructure for scale, distribution, tenancy, governance, or compatibility.

The installed CLI and planned local MCP path—stdio between client and adapter, with CLI
subprocess invocation behind the adapter—assume a trusted caller, workspace, packaged
Operation set, and Aseprite installation. The current delivery plan has no standalone
REST API or remote HTTP service. HTTP is not prohibited in principle: an accepted
functional slice can add bounded Artifact/resource access or MCP transport as an Access
Projection over the same Published Language and Application use cases.

SPA does not add authentication, accounts, roles, authorization policy, audit-history
storage, event sourcing, distributed consistency or locks, generalized recovery
infrastructure, service governance, multi-tenancy, or a generic sandbox without a
functional requirement and observed operating need. A future network-facing slice must
state the trust and deployment boundary it actually creates and add only the supporting
behavior required by that boundary. Per-operation evidence, native transactions, staged
commit, target addressing, process control, and diagnostics remain part of the
functional behavior they support rather than becoming such platforms.
