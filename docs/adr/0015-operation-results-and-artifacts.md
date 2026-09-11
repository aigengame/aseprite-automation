---
status: accepted
---

# Keep inspection results operation-specific and artifact reporting simple

SPA does not introduce a common Observation base model. Each inspection or validation Operation publishes the Aseprite facts appropriate to its domain result: Sprite properties, Layers, Frames, Cels, pixels, Tilemap topology, Validation Findings, or other native concepts. Shared value types can be reused without forcing every read result through one abstraction.

Each inspection Operation defines its own typed Inspection Scope and reports the
normalized scope it actually evaluated. A successful inspection is complete for that
scope. A native empty collection is `[]`, and a missing optional native relationship
uses `null` only where its schema defines that meaning. Optional sections not requested
are identified explicitly rather than filled with empty values. A requested unsupported
capability or exceeded Domain Bound returns a typed Failure Envelope instead of partial
success.

When a domain supports windowed or chunked inspection, its Operation Result reports
the exact Rectangle, Frame Range, page, chunk, or other coverage returned and whether
the broader traversal is complete. A caller can also explicitly select an Artifact
projection when the Operation provides one. SPA does not silently truncate an
inspection or introduce a universal cursor, Inspection Result base class, or
Observation Envelope.

An Artifact is a file produced and verified by an Operation. Its public value contains `path`, `role`, `format`, `size_bytes`, and `sha256`. The byte digest identifies the exact bytes returned by this invocation and supports result verification; it does not create history, provenance, or an audit facility. A pixel digest appears only in a compare or validation result whose functional semantics require it.

Format-specific facts stay with the Operation Result that owns them. Image dimensions, frame ranges, sheet layout, tile count, and similar fields do not accumulate as optional fields on the common Artifact value. A preview is an export or render Operation that returns a PNG or GIF Artifact, not an Artifact subtype or preview service.

An Operation Result can contain `artifacts: Artifact[]`. SPA does not define an Artifact Record layer, an Artifact Manifest type, a persistent manifest file, an artifact catalog, or a provenance graph. Portable output files do not embed host-absolute or staging paths; the host-local path belongs to the returned Artifact value.

The Surface Manifest remains a different concept: it describes installed Operation contracts for discovery and MCP generation, not produced files. A caller or Asset Pipeline can combine Artifacts from multiple Operations or Sprites using its own evolving language and models.

A Selection remains an operation-specific value or Artifact used by Selection and
Selection-consuming Operations. It is not an Observation base model, persisted
Sprite child, or Artifact subtype. Results that produce a Selection report its
Canvas Pixel bounds and encoding facts in their own schema.
Inline Selection values and JSON Artifacts with role `selection-mask` carry the same
canonical Selection Encoding. A Selection PNG is reported as a Preview Artifact and
is not accepted as an equivalent authoritative mask without an explicit import and
threshold contract.
