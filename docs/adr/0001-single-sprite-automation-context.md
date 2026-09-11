---
status: accepted
---

# Keep one Sprite Automation bounded context

SPA uses one Sprite Automation bounded context because authoring, observation,
validation, and delivery share one language and change around the same Sprite
automation contract. Runtime integration, packaged Lua, CLI, MCP, Agent Skill,
inspection, validation, and export are modules or adapters rather than separate
bounded contexts. The repository therefore retains one root `CONTEXT.md` and does not
add an internal multi-context routing map.

Its external context relationships are directional:

- Aseprite is the upstream authority for native concepts and behavior such as Sprite,
  Layer, Frame, Cel, Image, Tileset, painting, filtering, color conversion, and export.
  SPA deliberately conforms to that native language and delegates native algorithms,
  while the Lua Operation Kernel and Aseprite adapter translate the public automation
  contract and contain headless API quirks, hidden state, and runtime differences.
- SPA owns agent-facing Sprite Automation semantics, including explicit targeting,
  composition, observation, Capability Gaps, postconditions, Target Commit, Operation
  Plans, Published Language, and Artifact facts. It publishes the CLI Open Host Service
  and Published Language to downstream consumers.
- Asset Pipeline is a downstream consumer. Its consumer-owned Anti-Corruption Layer
  translates SPA Operation Results, Failure Envelopes, and Artifacts into the pipeline
  contract accepted at integration time. SPA does not depend on validation-stage
  pipeline commands, types, or internal models.
- gda owns Godot import, engine, and runtime facts downstream of Asset Pipeline. It has
  no direct model dependency on SPA, and SPA validation cannot become Godot runtime
  evidence.

Cross-Sprite orchestration, output aggregation, installation, retry, and project
acceptance remain with the caller or Asset Pipeline. Reconsider another SPA bounded
context only after evidence shows an independent language, model, lifecycle, and reason
to evolve separately.
