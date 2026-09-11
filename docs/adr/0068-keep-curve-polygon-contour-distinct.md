# ADR-0068: Keep Curve, Polygon, and Contour as distinct native operations

## Status

Accepted

## Context

Aseprite exposes Curve, Polygon, and Contour as separate editor tools. Curve uses a
Four Points Controller and Bézier Intertwiner. Polygon uses a Point-by-Point
Controller and always-filled closure. Contour uses a Freehand Controller and closes
and fills the sampled contour.

Aseprite 1.3.18.5 `app.useTool` drives one press, zero or more movements, and one
release. That gesture does not evidently express Curve's four interaction phases or
Polygon's repeated clicks and completion. Contour's Freehand Controller can
potentially use the scripted gesture.

## Decision

- SPA retains three intended Aseprite-aligned Operations: `spa paint curve`,
  `spa paint polygon`, and `spa paint contour`.
- Applicable Point, Standard Paint Brush, Color Value, opacity, Ink, bounds,
  clipping, Selection, target, Linked Image, transaction, and result components can
  be shared.
- SPA does not introduce a universal Path, Segment, or Vector Shape domain model.
- Paint Curve preserves the native Four Points Controller and Bézier Intertwiner.
  Its ordered roles are start, first control Point, second control Point, and end.
- Paint Polygon preserves the native Point-by-Point Controller, ordered vertices,
  completion behavior, and always-filled closure.
- Paint Contour preserves one ordered native Freehand gesture and the tool's
  always-filled closed result. It is not a Polygon click sequence or outline mode.
- Curve and Polygon receive independent real Aseprite 1.3.18.5 headless capability
  probes before publishing Operation Descriptors.
- Contour receives an independent positive delivery gate because its Freehand
  Controller may be scriptable. A Curve or Polygon gap cannot block Contour.
- A failed probe yields only that Operation's version-specific Capability Gap.
- SPA does not replace any tool with custom Bézier evaluation, polygon scanline
  filling, GraphicsContext, Python geometry, or another Paint operation.

## Consequences

- Command names preserve the native controller and fill distinctions agents need.
- Shared scalar and geometry values do not force an invented vector-graphics model.
- Runtime limitations remain independently discoverable rather than collapsing a
  whole family of Paint capabilities.
- Contour can be delivered without solving native multi-click scripting first.

## Rejected alternatives

### Define one `paint path` operation

It would require SPA-defined segment, closure, and fill semantics that Aseprite does
not share across these tools.

### Implement Curve and Polygon directly in Lua

That would create a second geometry and raster authority.

### Gate all three tools together

Their controllers and scriptability differ, so a family-wide gate would hide useful
native capability.

### Treat Contour as Polygon

Freehand sampling and point-by-point vertices are distinct native inputs.
