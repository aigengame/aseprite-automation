---
status: accepted
---

# Prioritize the Core Domain and let functional requirements lead architecture growth

SPA's business capability is coextensive with Aseprite's: sprite creation, editing, inspection, validation, conversion, and export. SPA provides the agent-oriented control, composition, observation, and verifiable feedback needed to use those capabilities effectively. Functional requirements inside this envelope should deepen and broaden as evidence-bearing slices establish their behavior.

The boundary is functional versus non-functional, not native command versus extension. Typed operations, structured inspection, bounded plans, bulk authoring, validation, previews, and verifiable feedback can be functional extensions even when Aseprite does not expose those exact agent-facing forms. They remain inside the Aseprite capability envelope and directly advance sprite work.

Sprite Automation is SPA's Core Domain. It combines Aseprite-equivalent creation,
editing, inspection, validation, conversion, and export with the explicit control,
composition, observation, Capability Gaps, and verifiable results that make those
capabilities effective for agents. Core Domain delivery has the highest priority: SPA
first establishes usable end-to-end core behavior and then deepens and broadens it
through functional increments.

Aseprite Runtime Integration, Access Projection for CLI/MCP/Agent Skill, and Asset
Pipeline Integration are Supporting Subdomains. Domain-neutral framework and utility
capabilities such as CLI parsing, schema serialization, process primitives, file
operations, digests, and diagnostic capture are Generic Subdomains or implementation
infrastructure. Supporting and Generic capabilities follow current Core Domain needs.
They use enough design and abstraction to serve accepted functional slices, then evolve
when observed requirements change; they do not anticipate unsupported consumers,
generalize unproven variation, or introduce complexity disproportionate to current
functional value.

This problem-space classification does not relocate behavior authority. A packaged Lua
handler that implements an Operation's Core Operation Semantics belongs to the Core
Domain behavior even though the Kernel Protocol, process runner, and resource discovery
that execute it are Supporting mechanisms. Likewise, staged commit or Artifact
verification is part of a Core functional promise when an Operation depends on that
observable outcome; reusable filesystem mechanics remain technical support.

Non-functional requirements arise from accepted functional slices and observed operating needs. They must trace to the FR they support and remain proportionate to that need. NFR concerns do not receive an independent platform roadmap and do not justify speculative infrastructure for scale, distribution, tenancy, governance, or compatibility.

The current local CLI and subprocess MCP access path assume a trusted local caller, workspace, packaged operation set, and Aseprite installation. The host operating system and filesystem own caller identity and access. SPA does not add authentication, accounts, roles, RBAC, authorization policy, an audit or trace-history store, event sourcing, distributed consistency or locks, generalized concurrency or recovery infrastructure, service governance, multi-tenancy, or a generic sandbox. Remote HTTP remains outside the current product boundary rather than importing those concerns into the local tool.

These exclusions do not erase functional correctness. Per-operation structured results and evidence belong to result verification, not an audit platform. Aseprite document transactions and staged target commit belong to the promised edit outcome, not a distributed consistency system. Operation-specific target addressing and object identity belong to sprite editing semantics, not caller authentication. Process control and diagnostics belong to executing and observing an Operation, not service governance.

Every proposed Supporting, Generic, or NFR investment must answer which Core Domain FR
requires it, what observed need sets its depth, which boundary owns it, and what
acceptance evidence demonstrates its value. Without that trace, it does not displace
Core Domain delivery.
