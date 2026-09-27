---
status: accepted
---

# Define the Sprite Automation context and its external relationships

This decision consolidates ADR-0016.

[ADR-0095](0095-asset-preparation-authoring-and-delivery.md) refines input preparation
and delivery ownership within this same context. It preserves the external boundaries
below while assigning accepted raster preparation rules to SPA.

SPA uses one Sprite Automation bounded context because authoring, inspection,
validation, conversion, and export share Aseprite's object model and change around the
same agent-facing automation contract. Runtime integration, the Lua Operation Kernel,
CLI, MCP, Agent Skill, validation, and export are modules or adapters inside that
context, not independent bounded contexts.

The context has these directional relationships:

- Aseprite is the upstream language and behavior authority for native objects,
  operations, formats, and algorithms. SPA preserves that language and contains
  headless-runtime differences behind its public automation contract.
- SPA owns explicit targeting, orchestration, observation, validation, Capability
  Gaps, structured outcomes, and Artifact facts for sprite automation. Its CLI is the
  first exposure of the Open Host Service, and its schemas form the Published Language.
  MCP and any later accepted access transport project that language as inbound adapters;
  they do not own another capability or domain model.
- The gda Asset Pipeline is a downstream consumer. Its Anti-Corruption Layer translates
  the public SPA contract into pipeline concepts. SPA does not import pipeline-internal
  models or depend on its experimental command and type names.
- gda owns Godot import, engine, and runtime evidence. SPA validation cannot become a
  Godot runtime claim.

Cross-Sprite workflow, aggregation, installation, retry, and project acceptance remain
with the caller or Asset Pipeline. A new SPA bounded context is justified when evidence
shows an independent language, model, lifecycle, and reason to evolve separately.
