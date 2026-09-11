# ADR-0017: Keep the command catalog incremental and non-binding

- Status: Accepted
- Date: 2026-09-10

## Context

SPA needs a visible map of the Aseprite capability territory it intends to expose to
agents. Without one, command naming and grouping decisions are repeatedly rediscovered
inside individual issues. A catalog can also accumulate semantic lessons from vertical
slices in a form that is easier to navigate than issue history.

The catalog cannot safely become another authority for product requirements,
implementation status, architecture decisions, or public contracts. Those artifacts
have different lifecycles, and mixing their responsibilities makes detailed feature
design look like an accepted delivery commitment. A status-bearing or binding catalog
would duplicate those sources and drift from them.

The command surface is also intentionally not frozen before dogfooding. Exact names and
group boundaries should be able to improve when real Aseprite workflows expose a better
model.

## Decision

Maintain `docs/command-catalog.md` as an incremental, non-binding feature map.

The project artifacts have these distinct responsibilities:

- the umbrella PRD/SPEC owns product intent, scope, user outcomes, requirements, and
  prototype evidence;
- `CONTEXT.md` owns the concise ubiquitous-language glossary and bounded-context
  definitions;
- ADRs own durable, consequential decisions and the trade-offs that explain them;
- the command catalog owns non-binding capability territory, candidate navigation,
  and semantic notes that can seed later work;
- feature issues own what will be built in one vertical slice, including delivery
  priority, acceptance criteria, blockers, and milestone placement; and
- the installed Surface Manifest owns the Operations and public schemas that actually
  ship in that installation.

The catalog:

- records Command Group rules, candidate command spellings, intended capability
  territory, and semantic notes learned from accepted vertical slices;
- uses Aseprite's native nouns where Aseprite already defines the concept;
- distinguishes candidate design inputs from shipped Operations;
- contains no per-command implementation-status column;
- does not create an Operation Descriptor, public schema, compatibility promise, or
  delivery commitment merely by listing a command.

A candidate catalog entry or feature-specific design note does not become a delivery
commitment until a feature issue accepts it. A feature issue can cite the PRD, glossary,
ADRs, and catalog, but it must not redefine their cross-feature decisions. The installed
`spa schema` Surface Manifest remains the authority for the callable operation surface
and public contracts of that installation.

When a vertical slice changes the intended surface or establishes durable semantic
behavior, its implementation should reconcile the catalog description. This records
what was learned without turning the catalog into a second task tracker or runtime
registry.

## Consequences

- Contributors and agents get one navigable map of the intended product territory.
- Strategic architecture and feature delivery can evolve without occupying the same
  document or lifecycle.
- Early command names and group boundaries can evolve without pretending to be shipped
  compatibility commitments.
- Shipped capability checks remain mechanical: query the installed Surface Manifest.
- Work-status checks remain social and project-specific: query the issue tracker.
- Catalog entries need periodic semantic reconciliation, but never status bookkeeping.
