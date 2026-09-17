# ADR-0060: Drive Paint primitives through a private Native Tool Invocation

## Status

Accepted

## Context

Aseprite's `app.useTool` invokes the editor's native Tools, while
`Image.context`/`GraphicsContext` uses a different graphics-path abstraction. Omitted
`app.useTool` options can fall back to active editor state and preferences.

SPA needs editor-equivalent Paint behavior with explicit agent inputs. The required
state control serves that functional outcome and must not grow into general session or
coordination infrastructure.

## Decision

- Native Tool Invocation is a private mechanism owned by the fixed Lua Operation
  Kernel. Each public Paint primitive keeps its own typed Operation Descriptor and
  fixed native tool. SPA does not expose a generic public `use-tool` command.
- The Kernel supplies the exact Cel, Layer, and Frame and every result-affecting option
  owned by the Operation. Active tool, colors, Brush, active site, and mutable tool
  preferences cannot provide omitted public semantics.
- Public primitive geometry uses Image Pixel space. The Kernel translates it through
  the addressed Cel position into native Canvas coordinates and validates the observed
  changed region before Target Commit.
- Native invocation cannot implicitly create a Cel, expand or move its Image, or break
  Image sharing. Cels on regular Transparent and Background Layers are supported under
  their existing postconditions; Reference, Tilemap, absent, and non-Cel targets require
  distinct Operations or fail. Linked Cel sharing remains intact.
- The Kernel captures and restores the editor/tool state changed for an invocation on
  success and failure. This is invocation-local functional isolation, not a persistent
  session, lock, concurrency, or generalized state-management subsystem.
- `app.useTool` remains the authority for native Paint pixels. GraphicsContext can be
  used for diagnostics or non-authoritative previews but cannot replace public native
  tool semantics. When a faithful native route is unavailable, SPA publishes a typed
  Capability Gap instead of switching raster authorities.
- Delivery evidence follows the Operation Determinism classification in ADR-0066:
  deterministic Operations prove native pixel parity; native-stochastic Operations
  prove native delegation, invariants, and complete actual-result observation.

## Consequences

- Public Paint commands preserve Aseprite editor vocabulary and pixel behavior.
- Agents receive typed Operations instead of a stateful editor escape hatch.
- Image geometry and linked relationships do not change as hidden drawing side effects.
- State isolation remains bounded to what native tool delegation functionally needs.

## Rejected alternatives

### Make `app.useTool` a generic public command

That would expose editor state and bypass operation-specific schemas and results.

### Use GraphicsContext as the Paint authority

Its path renderer is not the Aseprite pixel-tool semantic agents requested.

### Reimplement editor tools outside their native path

That would violate Lua Kernel authority and create a second raster engine.

## Consolidates

This ADR retains the cross-feature Native Tool Invocation decision previously repeated
by ADR-0061 through ADR-0065, ADR-0067, ADR-0069 through ADR-0071, and ADR-0073.
Issues #26 through #29 own the affected planned feature contracts, acceptance, required
runtime evidence, provenance links, curated evidence summaries, and planned handling of
candidate Capability Gaps. Tests and evidence artifacts own executed assertions and
results; the installed Surface Manifest owns installed Capability Gaps.
