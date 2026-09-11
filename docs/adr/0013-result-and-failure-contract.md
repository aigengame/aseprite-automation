---
status: accepted
---

# Publish disjoint Operation Results and Failure Envelopes

Every Operation publishes one success schema and participates in a uniform public failure channel. A successful CLI invocation exits zero and emits one schema-valid Operation Result in JSON mode. A failed invocation exits non-zero and emits one schema-valid Failure Envelope. Success models do not contain a `success: false` branch, and failures are not encoded as nominally successful results.

The Failure Envelope contains a stable machine-readable Failure Code, a broad Failure Category, and a human-readable message. It can identify the Operation and execution phase and can carry code-specific Failure Details or diagnostics when those facts change how an agent responds. Failure Details use a strict type associated with the code; SPA does not expose an arbitrary context dictionary or a universal sparse evidence object containing fields for unrelated failures.

Agents branch on Failure Code. Failure Category supports coarse exit behavior or policy. Messages and diagnostics explain the outcome but are not stable parsing surfaces. Human output is rendered from the same result or failure models rather than maintained as another behavior path.

A Validation Operation that completes and finds nonconformance returns an Operation Result containing Validation Findings. An unmet Plan Postcondition is a Failure Envelope because it aborts the plan and prevents target commit.

The Python adapter classifies the outcome using the Kernel Response, Aseprite launch result, captured diagnostics, and required Artifact facts. Aseprite's process exit code is classification input rather than the public verdict. MCP relays the same Failure Envelope losslessly through its error channel and does not translate it into a second error taxonomy.
