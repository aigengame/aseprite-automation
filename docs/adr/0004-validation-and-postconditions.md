---
status: accepted
---

# Treat Validation as read semantics and Postconditions as commit gates

Validation is a read-only Operation purpose, not a fifth Execution Kind, bounded context, or top-level command group. The four Execution Kinds remain `read`, `mutation`, `export`, and `script-run`; they classify side effects and trust. A Validation Operation belongs with the Aseprite domain concept whose facts it evaluates.

A completed Validation returns a structured result. Content that does not conform to a declared rule is represented by one or more Validation Findings and does not by itself mean that the Operation failed to execute. This lets callers inspect, aggregate, and apply policy to nonconformance without confusing it with launch, protocol, target-resolution, or other execution failures.

An Operation Plan has stronger semantics. A declared Postcondition is a commit gate: if it is not satisfied after its step or after the plan, the plan fails and its target is not committed. Request or schema invalidity is a Preflight failure before execution, not a Validation Finding.

This distinction keeps the structured result and failure channels stable. It also prevents a generic validation subsystem from taking ownership away from Sprite, Layer, Frame, Cel, Palette, Tileset, Artifact, and other concepts whose rules it would merely inspect.
