# ADR-0064: Preserve one native Pencil gesture

## Status

Accepted

## Context

Aseprite's Pencil tool consumes a sequence of Pointer samples as one freehand gesture.
Its Regular, Pixel-perfect, and Dots algorithms interpret that same sequence
differently. Preprocessing the path in SPA would create a second drawing semantic and
could prevent exact editor parity.

Aseprite 1.3.18.5's headless `app.useTool` path does not expose configurable Pointer
pressure, velocity, tilt, or complete Paint Dynamics. The source contains a Dots
Freehand Algorithm even though the public API documentation lists only values 0 and
1. Both areas need visible capability evidence rather than assumptions.

## Decision

- `spa paint pencil` invokes Aseprite's fixed `pencil` tool through Native Tool
  Invocation.
- It accepts one non-empty ordered Image Pixel `points` sequence and sends it as one
  native press/move/release gesture. A one-Point sequence is valid.
- SPA preserves Point order and multiplicity. It does not deduplicate, simplify,
  resample, interpolate, close, or otherwise normalize the sequence.
- The request requires Standard Paint Brush, compatible Color Value, integer opacity
  in `0..255`, an accepted Ink, and explicit Aseprite Freehand Algorithm `regular`,
  `pixel-perfect`, or `dots`.
- Aseprite's selected algorithm is authoritative for pixels between and at supplied
  Points. The request does not claim that each Point changes a pixel.
- Existing actual-Brush-footprint bounds, explicit clipping, Selection Application,
  no-implicit-Cel-or-Image-change, Background, Linked Image, transaction, and
  postcondition rules apply.
- Pencil does not absorb the native Line, Spray, or Eraser tools. Image Brush and
  Shading Ink retain their separate intended-capability contracts and gates.
- Paint Dynamics remain an intended functional Capability Gap until a real native
  route can explicitly supply and verify pressure, velocity, tilt, dynamic size,
  angle, gradient, and related inputs. SPA cannot inherit GUI Dynamics or simulate
  them in Python or alternate Lua drawing code.
- Regular, Pixel-perfect, and Dots have independent real `aseprite --script`
  editor-parity gates. Dots must prove the source-enum behavior despite its omission
  from the public API's documented `0|1` values.
- Failure of one algorithm returns its typed Capability Gap without hiding the
  algorithms that passed their gates.
- Results return the exact input Points, Freehand Algorithm, normalized Brush/Ink/
  opacity, requested and actual native coverage, clipping and Selection counts,
  every affected Cel/link, and before/after content digest. Save/close/reopen verifies
  persisted facts.

## Consequences

- Agents can reproduce a Pencil gesture without SPA inventing path geometry.
- Algorithm-specific availability is honest when documentation and source differ.
- Paint Dynamics stay on the functional roadmap without contaminating current
  requests with implicit or fabricated input.
- Line, Spray, and Eraser can preserve their distinct native tool semantics.

## Rejected alternatives

### Name the command `paint stroke`

It would replace Aseprite's specific Pencil vocabulary with a broader SPA term and
blur the boundaries of Line, Spray, and Eraser.

### Normalize Point paths before invocation

That would change the input observed by Aseprite's Freehand Algorithms.

### Treat Dots as documented support without evidence

The exact source and public API disagree, so a real headless proof is required.

### Simulate Paint Dynamics

SPA would become the authority for behavior that belongs to Aseprite's drawing
engine.
