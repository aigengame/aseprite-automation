---
status: accepted
---

# Publish distinct Operation outcomes and verified Artifacts

This decision consolidates ADR-0015.

Every Operation publishes one success schema and participates in one public failure
channel. A successful CLI invocation exits zero and emits a schema-valid Operation
Result in JSON mode. A failed invocation exits non-zero and emits a schema-valid
Failure Envelope. Success models do not contain failure branches, and failures are not
encoded as nominal success.

Failure Envelopes contain a stable Failure Code, a broad Failure Category, and a human
message. Typed code-specific details and diagnostics are present when they affect
recovery. Agents branch on the code; categories support coarse policy; messages and
diagnostics are explanatory rather than stable parsing surfaces. Human output is
rendered from the same models, and MCP relays the same outcome taxonomy.

Inspection and Validation Results report the native facts appropriate to their domain.
SPA does not impose a common Observation base model. Inspection completeness and bounds
follow ADR-0008. A completed Validation can return Findings as success; an execution
failure or unmet Plan Postcondition returns a Failure Envelope.

An Artifact is a file produced and verified by an Operation. Its common public facts
are path, role, format, byte size, and SHA-256 digest. Format-specific facts remain in
the owning Operation Result. SPA does not add an Artifact Record layer, persistent
manifest, catalog, provenance graph, or audit history. The installed Surface Manifest
describes callable Operations and is not an output Artifact manifest.
