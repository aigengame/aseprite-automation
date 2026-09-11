# ADR-0070: Report the native Paint Curve controller gap

## Status

Accepted

## Context

Aseprite defines Curve as an unfilled Paint tool using a Four Points Controller,
Brush Point Shape, Bézier Intertwiner, and last-trace policy. Its four native roles
are the start, first control Point, second control Point, and end.

Aseprite 1.3.18.5 `app.useTool` represents one press, zero or more movements, and one
release. The Four Points Controller requires a multi-stage interaction that cannot be
completed by that call shape. The Lua API does not expose a separate Curve constructor
or a way to resume the same native Tool Loop across calls.

A real negative probe submitted two four-Point requests with identical endpoints and
materially different controls. Both vendor calls returned normally, both generated
zero opaque pixels, and the controls were not observable. A zero process exit is not
evidence that the Curve Operation occurred.

## Decision

- SPA retains `spa paint curve` as an intended deterministic Aseprite capability.
- Its future request contains exactly four ordered Image Pixel roles: `start`,
  `control1`, `control2`, and `end`.
- It requires Standard Paint Brush, compatible Color Value, opacity in `0..255`, and
  accepted Ink.
- It preserves native unfilled Curve semantics and accepts no fill, closure, Freehand
  Algorithm, generic Path, or arbitrary segment fields.
- On Aseprite 1.3.18.5, the Operation is absent from the Surface Manifest. `spa info`
  reports a typed Controller Capability Gap with runtime, native tool, controller, and
  probe evidence.
- A vendor call returning normally without an observable Curve cannot be projected as
  Operation success.
- A runtime can publish Paint Curve only when a supported native scripting route
  completes the Four Points Controller, makes all four roles independently observable,
  and passes editor-parity and persistence gates.
- Existing target, Brush, Color Mode, Ink, opacity, bounds, clipping, Selection,
  Background, Linked Image, transaction, and result rules apply when deliverable.
- SPA never ignores control Points, degrades Curve to Line, drives GUI pointer input,
  invokes GraphicsContext, or evaluates/rasterizes Bézier geometry in Lua or Python.

## Consequences

- The intended Aseprite-equivalent capability remains visible without advertising a
  command that silently does nothing.
- Runtime discovery tells agents why Curve is unavailable and which native boundary
  must change.
- Successful process execution remains subordinate to verified Operation
  postconditions.
- A future native scripting improvement can activate the descriptor without changing
  Curve's Published Language.

## Rejected alternatives

### Publish the current zero-effect invocation

It would turn vendor process success into a false semantic success.

### Ignore the two control Points

The result would be a Line-like operation mislabeled as native Curve.

### Simulate the controller with GUI automation

SPA automates Aseprite through its scripting boundary and does not reproduce editor
mouse interaction or depend on a display session.

### Implement Bézier rasterization in the Operation Kernel or Python

That would create a second Curve and raster authority instead of exposing Aseprite's
business capability.
