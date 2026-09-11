# ADR-0069: Define Paint Contour as one native filled Freehand gesture

## Status

Accepted

## Context

Aseprite defines Contour with its native `contour` tool, Paint Ink, Freehand
Controller, Brush Point Shape, line intertwiner, accumulate trace policy, and
always-filled behavior. On the final tool-loop step, the native intertwiner closes
and fills the accumulated stroke.

Aseprite 1.3.18.5 `app.useTool` can represent one press, zero or more movements, and
one release from a non-empty Point sequence. Its public API documents Freehand
Algorithm values 0 and 1, corresponding to Regular and Pixel-perfect. The source also
contains a `DOTS` enum value, but the editor field marks it unavailable and the public
API does not promise it for Contour. Headless scripting does not provide GUI Paint
Dynamics or configurable pointer pressure, velocity, and tilt.

Discovery proved basic headless reachability and distinct Regular and Pixel-perfect
results. Issue #28 owns the detailed probe evidence and delivery acceptance.

## Decision

- `spa paint contour` declares `deterministic` Operation Determinism and invokes only
  Aseprite's native `contour` tool through the fixed Lua Operation Kernel.
- The request contains one non-empty ordered Image Pixel Point sequence. SPA preserves
  order and multiplicity as one native press/move/release gesture. One Point remains
  valid native input.
- SPA does not deduplicate, simplify, interpolate, resample, or pre-close the Points,
  and it does not reinterpret them as Polygon vertices.
- The request requires Standard Paint Brush, compatible Color Value, opacity in
  `0..255`, accepted Ink, and `regular` or `pixel-perfect` Freehand Algorithm.
- Regular and Pixel-perfect retain their native boundary-processing semantics. The
  native Contour tool remains authoritative for closure, fill, and raster coverage.
- Closure and fill are fixed Operation behavior. The request has no `closed`,
  `filled`, `outline`, generic Path, or public mouse-button fields.
- The source-internal `dots` value is not exposed for Contour because it is neither an
  available editor setting nor part of the documented 1.3.18.5 `app.useTool` contract.
- Paint Dynamics, pressure, velocity, and tilt remain a functional Capability Gap;
  SPA does not simulate them.
- Existing target, Brush-footprint bounds, clipping, Selection Application,
  Background, Linked Image, transaction, and persistence rules apply.
- Results report exact Points, algorithm, normalized Brush/Color/Ink/opacity,
  requested and actual coverage, all affected Cels/links, changed count, and
  before/after content digest.
- Issue #28 owns the complete real-runtime editor-parity gate.
- No Lua/Python contour, closure, or polygon-fill implementation can substitute for
  native Contour.

## Consequences

- Contour can advance independently from the multi-stage Curve and Polygon tools.
- Agents receive the meaningful native controls without an invented Path model or
  meaningless open/outline variants.
- Operation-specific Freehand Algorithm values remain narrower than Pencil where the
  native editor and documented scripting surface differ.
- Native output, not a SPA geometry algorithm, defines degenerate and edge-case Point
  behavior.

## Rejected alternatives

### Expose `dots` because the C++ enum exists

That would promote an unavailable, undocumented internal state into SPA's Published
Language and would undermine Contour's filled-result contract.

### Require three or more Points

Aseprite accepts any non-empty scripted gesture. A SPA-defined geometry minimum would
replace native edge-case semantics without evidence.

### Add caller-selectable closure and fill modes

Those switches would turn Contour into a SPA-defined path primitive instead of the
native always-filled tool.

### Implement closure and filling in Lua or Python

That would violate the Lua Kernel DRY boundary and create a second raster authority.
