---
status: accepted
---

# Commit to Asset Pipeline integration without depending on its validation-stage design

SPA is committed to participating in the gda Asset Pipeline architecture as an external Aseprite automation system. The integration consumes SPA's public CLI, Published Language, Operation Results, Failure Envelopes, and Artifacts through an Asset Pipeline-owned anti-corruption adapter. SPA and gda do not import each other's internal models.

The gda Asset Pipeline is still under validation and has not joined gda's main branch. Its current command names, package names, tactical types, producer interfaces, receipts, and workflow vocabulary are informative rather than normative for SPA. SPA does not copy those names into its ubiquitous language or public schemas and does not shape its internal modules around them.

The stable architectural commitment is directional. SPA owns Aseprite-equivalent sprite creation, editing, inspection, validation, conversion, and export behavior. The outer Asset Pipeline owns cross-tool and cross-Sprite workflow, adaptation, output aggregation, installation, and project-level acceptance. gda owns Godot import, engine, and runtime facts. Changes to the pipeline's commands or abstractions are absorbed by its consumer-side adapter rather than by SPA's public contract.

SPA therefore publishes a complete agent-facing CLI contract that remains useful independently of Asset Pipeline. Integration is validated against the Asset Pipeline contract that is accepted at implementation time; validation-stage command or type names are not compatibility promises.
