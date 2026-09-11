---
status: accepted
---

# Keep bounds and complete inspection semantics with Operations

This decision consolidates ADR-0026.

Each Operation owns the bounds and units intrinsic to its behavior. Raster Operations
can use pixel geometry, Tilemap Operations can use Tile Cell regions, and Operation
Plans can bound their Step count. SPA does not create a cross-domain budget ledger or
require every descriptor to register unrelated resource dimensions.

Each inspection Operation defines a typed domain-specific Inspection Scope and reports
the normalized scope it evaluated. Success is complete for that scope: SPA does not
silently truncate, sample, or omit promised facts. Results distinguish native absence,
an empty native collection, an unrequested section, an unsupported capability, and an
exceeded Domain Bound.

An Operation can expose an explicit window, chunk, page, or Artifact projection when
its data requires one. A successful bounded result reports exact Inspection Coverage
and whether broader traversal is complete. Coverage and continuation semantics remain
operation-specific rather than forming a universal cursor, Observation Envelope, or
Inspection Result base model.

Exceeding a Domain Bound returns a typed failure with the applicable allowed range.
The Aseprite adapter separately owns process timeout and captured-output Execution
Guards. These guards preserve execution and observation but do not create caller-facing
quotas or centralized resource governance.
