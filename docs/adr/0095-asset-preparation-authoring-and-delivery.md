---
status: accepted
---

# Separate asset preparation, sprite authoring, and asset delivery ownership

The owner accepted this direction after the procedural and hybrid wizard examples.
Issue [#102](https://github.com/aigengame/aseprite-automation/issues/102) tracks its
documentation and planning reconciliation. This decision refines the strategic
classification in ADR-0007 and input relationships in ADR-0001. Both decisions remain
active in their unaffected scope; `CONTEXT.md` states the current model.

## Evidence and problem

The [procedural wizard](../../examples/wizard_cast/DOGFOODING.md) combines pixel art,
motion sampling, native authoring, and component delivery in a finite recipe. The
[hybrid wizard](../../examples/wizard_cast_v2/DOGFOODING.md) adds selected generated
inputs, deterministic raster preparation, explicit foot and attachment landmarks,
and frozen source/result evidence. These activities have different reasons to change.

The hybrid experiment reproduced prepared inputs and native output, while its five
poses still needed artistic alignment and visual review. The examples show a need for
reusable preparation and bounded authoring; they do not validate a general animation
engine, automatic in-between anatomy, or a production preparation API. Their temporary
color-matching algorithm is evidence of work to perform, not a native color contract.

## Decision

Keep one Sprite Automation Bounded Context. Classify the accepted responsibilities as:

- **Sprite Authoring Core Domain:** verifiable Sprite and animation creation,
  editing, composition, observation, and validation. Document and Animation owns
  bounded Frame/Cel motion authoring. Raster Authoring, Color and Palette, and Tile
  Authoring retain their native semantic ownership. Static Sprite work stays in scope.
- **Asset Preparation Supporting Subdomain:** a caller-declared Preparation
  Specification, explicit raster geometry and Input Anchors, preparation validation,
  and Frozen Input and Prepared Raster facts. Preparation selects and composes
  accepted transformations through their owners. It does not implement a parallel
  native Image or color engine.
- **Asset Delivery Supporting Subdomain:** the existing Delivery responsibility for
  format-specific export, complete destination sets, independent Artifact validation,
  and truthful publication outcomes. Reclassify that responsibility without creating
  a second exporter or weakening its contracts.

Runtime Integration, Access Projection, Asset Pipeline Integration, and the Generic
Subdomain keep their existing roles. Supporting status describes strategic investment;
it does not mean that a capability has no domain rules or weaker acceptance.

### Place rules by meaning, not workflow position

Preparation owns a requested size, palette policy, transparency policy, and explicit
anchor treatment. The existing Image, Color, and Palette owners define the applicable
native transformations. An export can use those same semantics after authoring without
returning to a preparation stage or duplicating the algorithms. The first preparation
slice must establish its accepted transformations and prerequisites before AFK work.

Artwork Recipes retain selected poses, appearance, casting rhythm, particle paths, and
other art decisions. Bounded Motion Authoring owns explicit time/Frame mapping,
interpolation, rounding, and use of the existing Frame/Cel rules. It must specify
copy/link behavior, occupied targets, and persisted verification in its feature issue.
Numeric continuity does not establish natural anatomical motion or visual quality.

Native save/reopen verification and Target Commit remain part of mutation completion
under ADR-0014. A successful Cel edit is persisted even if the caller never exports.
Asset Delivery follows ADR-0085: validate the complete staged output set, then publish
with truthful per-destination failure facts. Multi-file publication is not an atomic
transaction and can return `partial_publication`.

Document and Animation owns the meaning of animation comparison and continuity
inspection. Asset Delivery owns the Preview Artifact's export and publication rules.
The existing animation preview use case composes those owners; its physical location
does not create a second preview implementation.

### Keep execution authority independent of strategic classification

The established terms Ordinary Core Operation and Core Operation Semantics identify
the fixed packaged execution model in ADR-0010. They do not restrict native Operations
to the Core Domain. Native Asset Delivery behavior still executes through its fixed
packaged handler and Aseprite; moving it to a Supporting Subdomain does not authorize
generated Lua, a Python compositor, or a `script run` proxy.

An application-only preparation capability can own source identity, declared anchors,
and result coordination without inventing an Aseprite handler for those facts. Any
native transformation it invokes remains with the corresponding packaged owner.
Descriptors continue to declare actual execution binding, side effects, and Plan
eligibility. This decision adds no execution kind, Operation, or implicit Plan support.

### Keep external integration boundaries explicit

Generation tools and artists supply selected input bytes and art decisions. SPA owns
the accepted preparation, authoring, and delivery contracts. Callers and the downstream
Asset Pipeline own cross-tool and cross-Sprite workflow, project file-role mapping,
installation, retry, and project acceptance. gda owns Godot import and runtime evidence.

An ACL translates a genuinely different external model. The downstream-owned SPA ACL
remains one such boundary. Ordinary raster input needs a bounded input adapter; no
generation-provider integration is required by this decision. Internal SPA modules
share language through directed contracts. Production never depends on example code.

Freezing means retaining selected bytes, choices, and content digests and checking them
on rebuild. It does not add a registry, background service, persistent run lifecycle,
generation credentials, or automatic regeneration to normal builds.

## Incremental implementation and open claims

Each feature remains a complete, separately verifiable slice. Existing native import,
Image observation, component export, and sequence export issues retain their owners.
New issues track preparation, bounded motion, and the measured gaps without expanding
the completed examples' contracts. A module is added when its slice needs it; there is
no preparatory package rewrite or generic workflow engine.

| Structural claim | Current evidence and limit | Validation or disconfirming condition |
| --- | --- | --- |
| Preparation can hide reusable input work behind an explicit contract. | v2 reproduces one declared palette/alpha/geometry treatment. Broader contract remains open. | Use a wizard input and a different raster with explicit anchors. If both require artwork-specific rules inside the module, narrow its contract. |
| Bounded motion can reuse Frame/Cel semantics without taking over art direction. | v1/v2 separate numeric motion from selected poses. Public authoring contract remains open. | Start with an existing Cel and position/opacity keys; use wizard and floating-emblem cases. Inspect reopened Frame/Cel and pixel facts; keep visual acceptance separate. |
| Delivery can evolve as a Supporting Subdomain while preserving guarantees. | Static PNG and continuity Preview already have verified publication behavior. New formats remain gated by their issues. | Retain native rendering, Source preservation, complete staged-set checks, and applicable partial-publication tests. |
| Fewer persisted invocations may reduce authoring cost. | Both examples measure repeated Cel writes; concurrent and different-size runs are not controlled speedup evidence. | Measure the same fixture and runtime before/after a bounded Plan slice; do not trade away failure non-commit or persisted verification. |

Strategic ownership is accepted; the open claims above do not establish installed
support or automatic performance improvements. Feature issues own exact contracts and
their real blockers. Preparation, existing-Cel motion, import, and delivery need not
form one mandatory implementation chain.

Follow-up contracts are tracked in [#103](https://github.com/aigengame/aseprite-automation/issues/103)
(preparation), [#104](https://github.com/aigengame/aseprite-automation/issues/104)
(bounded motion), and [#105](https://github.com/aigengame/aseprite-automation/issues/105)
(existing Cel updates in Plans). The small initial Image geometry candidate is #106;
full-E2E capacity is #107. These links identify owners, not extra strategic invariants.

## Alternatives and consequences

- Keeping all preparation in examples repeats input policy and verification work.
  The selected approach admits only bounded, demonstrated responsibilities into SPA.
- Assigning all motion to preprocess separates Frame/Cel rules from their native
  owners. Keep reusable authoring in the Core and concrete art choices in recipes.
- Assigning native save to postprocess makes mutation completion depend on a later
  workflow step. Preserve mutation and export as separate completion boundaries.
- Separate contexts or ACLs for every stage add translation without demonstrated
  language differences. Keep the current context and compact physical layout.

The integrated module and dependency view belongs in `ARCHITECTURE.md`. The PRD owns
product outcomes; feature issues own exact scope and evidence. Existing story numbers,
public contracts, and native semantic decisions remain stable unless a feature makes
an explicit, separately reviewed change.

## References

- [Fowler: Bounded Context](https://martinfowler.com/bliki/BoundedContext.html)
- [Microsoft: Anti-Corruption Layer](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer)
