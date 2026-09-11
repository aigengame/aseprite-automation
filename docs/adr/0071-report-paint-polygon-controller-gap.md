# ADR-0071: Report the native Paint Polygon controller gap

## Status

Accepted

## Context

Aseprite defines Polygon as a Paint tool using a Point-by-Point Controller, Brush
Point Shape, line intertwiner, last-trace policy, and always-filled behavior. The
controller accumulates vertices through distinct interaction phases and owns the
completion action.

Aseprite 1.3.18.5 `app.useTool` represents one press, zero or more movements, and one
release. During that gesture the Point-by-Point Controller retains the initial Point
and replaces one provisional endpoint; it cannot receive the additional presses that
commit intermediate vertices.

A real negative probe varied intermediate vertices while preserving the endpoints.
Both calls returned normally, both produced zero opaque pixels, and the intermediate
vertices were not observable. Repeating the initial vertex at the end to force the
controller's completion condition instead filled all 400 pixels of the 20-by-20 probe
canvas. Synthetic closure is not a safe invocation protocol.

## Decision

- SPA retains `spa paint polygon` as an intended deterministic Aseprite capability.
- Its future request contains ordered Image Pixel `vertices`, Standard Paint Brush,
  compatible Color Value, opacity in `0..255`, and accepted Ink.
- The native Point-by-Point Controller owns accumulation and completion; the native
  Polygon owns closure, filling, Brush coverage, cardinality, and degenerate behavior.
- The request accepts no open/outline switch, explicit closing Point, Freehand
  Algorithm, mouse-event stream, or generic Path fields.
- On Aseprite 1.3.18.5, the Operation is absent from the Surface Manifest. `spa info`
  reports a typed Controller Capability Gap with runtime, native tool, controller, and
  probe evidence.
- A vendor call returning normally without observable vertices and a completed filled
  Polygon cannot be projected as Operation success.
- A runtime can publish Paint Polygon when a supported native scripting route makes
  every vertex and completion independently observable and passes editor-parity and
  persistence gates.
- The delivery slice derives accepted vertex cardinalities and degenerate cases from
  real native editor behavior rather than adding SPA geometry rules.
- Existing target, Brush, Color Mode, Ink, opacity, bounds, clipping, Selection,
  Background, Linked Image, transaction, and result rules apply when deliverable.
- SPA never repeats the first vertex as a completion sentinel, chains separate native
  Tool Loops, aliases Contour, drives GUI input, invokes GraphicsContext, or fills a
  polygon in Lua or Python.

## Consequences

- The intended Aseprite-equivalent capability remains visible without exposing an
  incomplete or destructive command.
- The explicit-closing negative case prevents agents from inferring a conventional
  polygon encoding that the vendor API does not support.
- Runtime discovery identifies the native controller boundary that blocks delivery.
- Future native API support can activate the Operation without turning it into a
  SPA-defined Path abstraction.

## Rejected alternatives

### Repeat the first vertex to signal completion

The real 1.3.18.5 probe filled the entire canvas rather than the requested Polygon.

### Invoke `app.useTool` once per vertex

Each call creates and commits an independent Tool Loop; it does not continue the same
Point-by-Point Controller state.

### Treat Polygon as Contour

Point-by-Point vertices and one sampled Freehand gesture are different native inputs.

### Implement polygon closure and filling in Lua or Python

That would create a second Polygon and raster authority.
